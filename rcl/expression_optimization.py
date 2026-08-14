from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .expression_history import (
    expression_sha256,
    validate_behavior_expression_history_metadata,
    validate_expression_object,
)
from .intent import validate_behavior_intent_metadata
from .profile import PAYLOADS, RCLProfile, RCLValidationError, validate_schema
from .profile_diff import diff_profiles


EXPRESSION_OPTIMIZATION_VERSION = "0.1"
EXPRESSION_OPTIMIZATION_PATCH_METHOD = "rcl.expression.optimization.patch.v0.1"
EXPRESSION_OPTIMIZATION_APPLY_METHOD = "rcl.expression.optimization.apply.v0.1"


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if result.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_hashes(profile: RCLProfile) -> dict[str, str]:
    return {name: _sha256_file(profile.root / name) for name in PAYLOADS}


def _source_profile_id(profile: RCLProfile) -> str | None:
    manifest_path = profile.root / "manifest.json"
    if not manifest_path.exists():
        return None
    return profile.load("manifest.json")["profile_id"]


def _profile_ref(profile: RCLProfile) -> dict[str, Any]:
    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")
    return {
        "robot_id": identity["robot_id"],
        "continuity_generation": identity["continuity_generation"],
        "embodiment_id": embodiment["embodiment_id"],
    }


def _find_behavior(payload: dict[str, Any], behavior_id: str) -> dict[str, Any]:
    for behavior in payload["behaviors"]:
        if behavior["behavior_id"] == behavior_id:
            return behavior
    raise RCLValidationError(f"Behavior not found: {behavior_id}")


def _validate_candidate(
    profile: RCLProfile,
    candidate: dict[str, Any],
    behavior_id: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    validate_schema(candidate, "expression-optimization-candidate")
    _parse_datetime(candidate["created_at"], label="candidate.created_at")

    if candidate["behavior_id"] != behavior_id:
        raise RCLValidationError(
            f"Expression optimization candidate behavior {candidate['behavior_id']!r} "
            f"does not match behavior_id {behavior_id!r}"
        )

    behavior_payload = profile.load("behavior.json")
    behavior = _find_behavior(behavior_payload, behavior_id)
    current = behavior.get("expression")
    if current is None:
        raise RCLValidationError(
            f"{behavior_id}: expression optimization requires an active expression"
        )

    actual_current_sha = expression_sha256(current)
    if candidate["current_expression_sha256"] != actual_current_sha:
        raise RCLValidationError(
            "Expression optimization candidate is stale: current expression digest does not match"
        )

    action = candidate["action"]
    replacement = candidate["replacement_expression"]
    if action == "remove":
        if replacement is not None:
            raise RCLValidationError("remove candidate must use replacement_expression=null")
        return behavior, None

    if not isinstance(replacement, dict):
        raise RCLValidationError("simplify candidate requires a complete replacement_expression")
    validate_expression_object(replacement, behavior_id=behavior_id)
    if expression_sha256(replacement) == actual_current_sha:
        raise RCLValidationError("simplify candidate is a semantic no-op")

    synthetic = copy.deepcopy(behavior_payload)
    synthetic_behavior = _find_behavior(synthetic, behavior_id)
    synthetic_behavior["expression"] = copy.deepcopy(replacement)
    validate_schema(synthetic, "behavior")
    validate_behavior_intent_metadata(synthetic)
    return behavior, replacement


def _optimization_id(
    *,
    behavior_id: str,
    candidate_sha256: str,
    approved_at: str,
    approved_by: str | None,
) -> str:
    material = {
        "behavior_id": behavior_id,
        "candidate_sha256": candidate_sha256,
        "approved_at": approved_at,
        "approved_by": approved_by,
    }
    return f"expr-opt-{_sha256_json(material)[:16]}"


def preview_expression_optimization(
    profile: RCLProfile,
    candidate: dict[str, Any],
    behavior_id: str,
    *,
    approved_at: str,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic expression optimization patch without mutation."""

    behavior, replacement = _validate_candidate(profile, candidate, behavior_id)
    approval_time = _parse_datetime(approved_at, label="approved_at")
    candidate_time = _parse_datetime(candidate["created_at"], label="candidate.created_at")
    if approval_time < candidate_time:
        raise RCLValidationError("approved_at cannot precede the optimization candidate timestamp")

    before_expression = copy.deepcopy(behavior["expression"])
    after_expression = copy.deepcopy(replacement)
    candidate_sha256 = _sha256_json(candidate)
    from_sha = expression_sha256(before_expression)
    to_sha = expression_sha256(after_expression)
    optimization_id = _optimization_id(
        behavior_id=behavior_id,
        candidate_sha256=candidate_sha256,
        approved_at=approved_at,
        approved_by=approved_by,
    )

    history_entry = {
        "optimization_id": optimization_id,
        "optimized_at": approved_at,
        "optimized_by": approved_by,
        "action": candidate["action"],
        "candidate_id": candidate["candidate_id"],
        "candidate_sha256": candidate_sha256,
        "reason": candidate["reason"],
        "evidence_refs": copy.deepcopy(candidate["evidence_refs"]),
        "from_expression_sha256": from_sha,
        "to_expression_sha256": to_sha,
        "expression_snapshot": before_expression,
    }

    patch = {
        "optimization_version": EXPRESSION_OPTIMIZATION_VERSION,
        "method": EXPRESSION_OPTIMIZATION_PATCH_METHOD,
        "behavior_id": behavior_id,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "source_profile": _profile_ref(profile),
        "source_behavior_sha256": _sha256_json(behavior),
        "candidate": {
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate_sha256,
            "created_at": candidate["created_at"],
            "action": candidate["action"],
            "reason": candidate["reason"],
            "evidence_refs": copy.deepcopy(candidate["evidence_refs"]),
        },
        "before_expression": before_expression,
        "after_expression": after_expression,
        "history_entry": history_entry,
    }
    validate_schema(patch, "expression-optimization-patch")
    return patch


def _apply_patch_to_behavior_payload(
    behavior_payload: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(behavior_payload)
    behavior = _find_behavior(result, patch["behavior_id"])
    if _sha256_json(behavior) != patch["source_behavior_sha256"]:
        raise RCLValidationError(
            "Expression optimization patch source behavior no longer matches the profile"
        )
    current = behavior.get("expression")
    if current is None or expression_sha256(current) != patch["history_entry"]["from_expression_sha256"]:
        raise RCLValidationError("Expression optimization patch current expression precondition failed")

    history = behavior.setdefault("expression_history", [])
    history.append(copy.deepcopy(patch["history_entry"]))
    if patch["after_expression"] is None:
        behavior.pop("expression", None)
    else:
        behavior["expression"] = copy.deepcopy(patch["after_expression"])

    validate_schema(result, "behavior")
    validate_behavior_intent_metadata(result)
    validate_behavior_expression_history_metadata(result)
    return result


def _derive_output_profile_id(profile: RCLProfile, patch: dict[str, Any]) -> str:
    identity = profile.load("identity.json")
    base = _source_profile_id(profile) or f"{identity['robot_id']}-g{identity['continuity_generation']}"
    return f"{base}-expression-{_sha256_json(patch)[:12]}"


def _assert_only_expression_changed(
    before_behavior: dict[str, Any],
    after_behavior: dict[str, Any],
    history_entry: dict[str, Any],
) -> None:
    before_history = copy.deepcopy(before_behavior.get("expression_history", []))
    after_history = copy.deepcopy(after_behavior.get("expression_history", []))
    if after_history != before_history + [history_entry]:
        raise RCLValidationError(
            "Expression optimization history must be append-only with exactly one new entry"
        )

    before = copy.deepcopy(before_behavior)
    after = copy.deepcopy(after_behavior)
    before.pop("expression", None)
    after.pop("expression", None)
    before.pop("expression_history", None)
    after.pop("expression_history", None)
    if before != after:
        raise RCLValidationError(
            "Expression optimization changed fields outside expression/expression_history"
        )


def apply_expression_optimization(
    profile: RCLProfile,
    candidate: dict[str, Any],
    behavior_id: str,
    output_dir: str | Path,
    *,
    approved_at: str,
    approved_by: str | None = None,
    output_profile_id: str | None = None,
) -> dict[str, Any]:
    """Apply an approved expression optimization into a new immutable snapshot."""

    patch = preview_expression_optimization(
        profile,
        candidate,
        behavior_id,
        approved_at=approved_at,
        approved_by=approved_by,
    )
    output = Path(output_dir)
    if output.exists():
        raise RCLValidationError(f"Output snapshot already exists: {output}")

    source_root = profile.root.resolve()
    intended = output.resolve()
    if intended == source_root or source_root in intended.parents:
        raise RCLValidationError("Output snapshot must not be created inside the source profile")

    before_hashes = _payload_hashes(profile)
    before_payload = profile.load("behavior.json")
    before_behavior = copy.deepcopy(_find_behavior(before_payload, behavior_id))

    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=str(output.parent)))

    try:
        for payload_name in PAYLOADS:
            shutil.copyfile(profile.root / payload_name, temp / payload_name)

        updated_behavior = _apply_patch_to_behavior_payload(before_payload, patch)
        (temp / "behavior.json").write_text(
            json.dumps(updated_behavior, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        new_profile_id = output_profile_id or _derive_output_profile_id(profile, patch)
        manifest = RCLProfile.create_manifest(temp, new_profile_id, approved_at)
        validate_schema(manifest, "manifest")
        (temp / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        output_profile = RCLProfile.open(temp)
        after_behavior = _find_behavior(output_profile.load("behavior.json"), behavior_id)
        _assert_only_expression_changed(
            before_behavior,
            after_behavior,
            patch["history_entry"],
        )

        diff = diff_profiles(profile, output_profile)
        if diff["summary"] != {
            "added_behaviors": 0,
            "removed_behaviors": 0,
            "modified_behaviors": 1,
        }:
            raise RCLValidationError(
                "Expression optimization produced changes outside the selected behavior"
            )
        if len(diff["behavior_changes"]) != 1 or diff["behavior_changes"][0]["behavior_id"] != behavior_id:
            raise RCLValidationError(
                "Expression optimization diff does not match the selected behavior"
            )
        if diff["behavior_changes"][0]["parameter_changes"]:
            raise RCLValidationError(
                "Expression optimization must not modify semantic behavior parameters"
            )

        after_hashes = _payload_hashes(profile)
        if before_hashes != after_hashes:
            raise RCLValidationError(
                "Source profile changed while applying expression optimization"
            )

        result = {
            "optimization_version": EXPRESSION_OPTIMIZATION_VERSION,
            "method": EXPRESSION_OPTIMIZATION_APPLY_METHOD,
            "created_at": approved_at,
            "behavior_id": behavior_id,
            "action": candidate["action"],
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": patch["candidate"]["candidate_sha256"],
            "patch_sha256": _sha256_json(patch),
            "source_robot_id": profile.load("identity.json")["robot_id"],
            "source_profile_id": _source_profile_id(profile),
            "output_profile_id": new_profile_id,
            "output_path": str(output),
            "source_unchanged": True,
            "output_valid": True,
            "diff_summary": diff["summary"],
            "disclaimer": (
                "This result records an explicitly approved continuity-expression optimization. "
                "It does not prove that removal is safe, change functional Intent, authorize safety bypass, "
                "or delete the historical expression snapshot."
            ),
        }
        validate_schema(result, "expression-optimization-result")
        temp.rename(output)
        return result
    except Exception:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        raise
