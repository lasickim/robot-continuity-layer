from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .intent import validate_behavior_intent_metadata
from .profile import PAYLOADS, RCLProfile, RCLValidationError, validate_schema
from .profile_diff import diff_profiles


INTENT_APPROVAL_VERSION = "0.1"
INTENT_APPROVAL_PATCH_METHOD = "rcl.intent.approval.patch.v0.1"
INTENT_APPROVAL_APPLY_METHOD = "rcl.intent.approval.apply.v0.1"


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


def _validate_candidate_report(
    profile: RCLProfile,
    candidate_report: dict[str, Any],
    behavior_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_schema(candidate_report, "intent-candidate-report")

    if candidate_report["status"] != "candidate":
        raise RCLValidationError("Intent discovery report is not an approvable candidate")
    if candidate_report["recommended_next_action"] != "review_candidate":
        raise RCLValidationError("Intent discovery report is not ready for candidate review")
    if candidate_report["confidence"] not in {"moderate", "strong"}:
        raise RCLValidationError("Intent discovery candidate has insufficient evidence confidence")
    if candidate_report["causal_claim"] is not False:
        raise RCLValidationError("Intent approval requires causal_claim=false")
    if not candidate_report["gates"] or not all(gate["passed"] for gate in candidate_report["gates"]):
        raise RCLValidationError("Intent discovery candidate contains failed evidence gates")

    hypothesis = candidate_report["hypothesis"]
    if hypothesis["candidate_action_id"] != behavior_id:
        raise RCLValidationError(
            f"Intent candidate action {hypothesis['candidate_action_id']!r} does not match behavior_id {behavior_id!r}"
        )

    behavior_payload = profile.load("behavior.json")
    behavior = _find_behavior(behavior_payload, behavior_id)
    if behavior.get("intent") is not None:
        raise RCLValidationError(
            f"{behavior_id}: v0.1 intent approval will not overwrite an existing intent"
        )

    synthetic = copy.deepcopy(behavior_payload)
    synthetic_behavior = _find_behavior(synthetic, behavior_id)
    synthetic_behavior["intent"] = copy.deepcopy(hypothesis["proposed_intent"])
    validate_schema(synthetic, "behavior")
    validate_behavior_intent_metadata(synthetic)
    return hypothesis, behavior


def preview_intent_approval(
    profile: RCLProfile,
    candidate_report: dict[str, Any],
    behavior_id: str,
    *,
    approved_at: str,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic intent attachment patch without mutating the source profile."""

    hypothesis, behavior = _validate_candidate_report(profile, candidate_report, behavior_id)
    approval_time = _parse_datetime(approved_at, label="approved_at")
    candidate_time = _parse_datetime(candidate_report["created_at"], label="candidate_report.created_at")
    if approval_time < candidate_time:
        raise RCLValidationError("approved_at cannot precede the Intent Candidate report timestamp")

    candidate_report_sha256 = _sha256_json(candidate_report)
    source_behavior_sha256 = _sha256_json(behavior)
    policy = candidate_report["policy"]
    intent = copy.deepcopy(hypothesis["proposed_intent"])
    intent["provenance"] = {
        "source": "discovered",
        "candidate_id": candidate_report["candidate_id"],
        "dataset_id": candidate_report["dataset_id"],
        "discovery_method": candidate_report["method"],
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "candidate_report_sha256": candidate_report_sha256,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "causal_claim": False,
    }

    patch = {
        "approval_version": INTENT_APPROVAL_VERSION,
        "method": INTENT_APPROVAL_PATCH_METHOD,
        "behavior_id": behavior_id,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "source_profile": _profile_ref(profile),
        "source_behavior_sha256": source_behavior_sha256,
        "candidate": {
            "candidate_id": candidate_report["candidate_id"],
            "dataset_id": candidate_report["dataset_id"],
            "discovery_method": candidate_report["method"],
            "candidate_report_sha256": candidate_report_sha256,
            "confidence": candidate_report["confidence"],
            "causal_claim": False,
        },
        "before_intent": None,
        "after_intent": intent,
    }
    validate_schema(patch, "intent-approval-patch")
    return patch


def _apply_patch_to_behavior_payload(
    behavior_payload: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(behavior_payload)
    behavior = _find_behavior(result, patch["behavior_id"])
    if behavior.get("intent") is not None:
        raise RCLValidationError("Intent approval patch target already has an intent")
    if _sha256_json(behavior) != patch["source_behavior_sha256"]:
        raise RCLValidationError("Intent approval patch source behavior no longer matches the profile")

    behavior["intent"] = copy.deepcopy(patch["after_intent"])
    validate_schema(result, "behavior")
    validate_behavior_intent_metadata(result)
    return result


def _derive_output_profile_id(profile: RCLProfile, patch: dict[str, Any]) -> str:
    identity = profile.load("identity.json")
    base = _source_profile_id(profile) or f"{identity['robot_id']}-g{identity['continuity_generation']}"
    return f"{base}-intent-{_sha256_json(patch)[:12]}"


def _assert_only_intent_changed(before_behavior: dict[str, Any], after_behavior: dict[str, Any]) -> None:
    before = copy.deepcopy(before_behavior)
    after = copy.deepcopy(after_behavior)
    after.pop("intent", None)
    if before != after:
        raise RCLValidationError("Intent approval changed fields outside behavior.intent")


def apply_intent_approval(
    profile: RCLProfile,
    candidate_report: dict[str, Any],
    behavior_id: str,
    output_dir: str | Path,
    *,
    approved_at: str,
    approved_by: str | None = None,
    output_profile_id: str | None = None,
) -> dict[str, Any]:
    """Apply an eligible Intent Candidate into a new validated snapshot directory."""

    patch = preview_intent_approval(
        profile,
        candidate_report,
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
        _assert_only_intent_changed(before_behavior, after_behavior)

        diff = diff_profiles(profile, output_profile)
        if diff["summary"] != {
            "added_behaviors": 0,
            "removed_behaviors": 0,
            "modified_behaviors": 1,
        }:
            raise RCLValidationError("Intent approval produced changes outside the selected behavior")
        if len(diff["behavior_changes"]) != 1 or diff["behavior_changes"][0]["behavior_id"] != behavior_id:
            raise RCLValidationError("Intent approval diff does not match the selected behavior")
        if diff["behavior_changes"][0]["parameter_changes"]:
            raise RCLValidationError("Intent approval must not modify semantic behavior parameters")

        after_hashes = _payload_hashes(profile)
        if before_hashes != after_hashes:
            raise RCLValidationError("Source profile changed while applying intent approval")

        result = {
            "approval_version": INTENT_APPROVAL_VERSION,
            "method": INTENT_APPROVAL_APPLY_METHOD,
            "created_at": approved_at,
            "behavior_id": behavior_id,
            "candidate_id": candidate_report["candidate_id"],
            "candidate_report_sha256": patch["candidate"]["candidate_report_sha256"],
            "patch_sha256": _sha256_json(patch),
            "source_robot_id": profile.load("identity.json")["robot_id"],
            "source_profile_id": _source_profile_id(profile),
            "output_profile_id": new_profile_id,
            "output_path": str(output),
            "source_unchanged": True,
            "output_valid": True,
            "diff_summary": diff["summary"],
            "causal_claim": False,
            "disclaimer": (
                "This result records an explicitly approved engineering intent hypothesis into a new RCL snapshot. "
                "It does not prove causality, subjective motivation, consciousness, identity, or safety."
            ),
        }
        validate_schema(result, "intent-approval-result")
        temp.rename(output)
        return result
    except Exception:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        raise
