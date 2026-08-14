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


INTENT_REVISION_VERSION = "0.1"
INTENT_REVISION_PATCH_METHOD = "rcl.intent.revision.patch.v0.1"
INTENT_REVISION_APPLY_METHOD = "rcl.intent.revision.apply.v0.1"


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


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if result.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return result


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


def _semantic_intent(intent: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(intent)
    result.pop("provenance", None)
    return result


def _validate_replacement_intent(behavior: dict[str, Any], replacement: dict[str, Any]) -> None:
    synthetic_behavior = copy.deepcopy(behavior)
    synthetic_behavior["intent"] = copy.deepcopy(replacement)
    synthetic_behavior.pop("intent_history", None)
    payload = {"behaviors": [synthetic_behavior]}
    validate_schema(payload, "behavior")
    validate_behavior_intent_metadata(payload)


def _latest_intent_timestamp(behavior: dict[str, Any]) -> datetime | None:
    timestamps: list[datetime] = []
    provenance = (behavior.get("intent") or {}).get("provenance")
    if isinstance(provenance, dict) and provenance.get("approved_at"):
        timestamps.append(_parse_datetime(provenance["approved_at"], label="intent.provenance.approved_at"))
    history = behavior.get("intent_history", [])
    if history:
        timestamps.append(
            _parse_datetime(history[-1]["revised_at"], label="intent_history[-1].revised_at")
        )
    return max(timestamps) if timestamps else None


def _validate_revision_candidate(
    profile: RCLProfile,
    candidate: dict[str, Any],
    behavior_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_schema(candidate, "intent-revision-candidate")
    if candidate["behavior_id"] != behavior_id:
        raise RCLValidationError(
            f"Intent revision candidate behavior {candidate['behavior_id']!r} does not match {behavior_id!r}"
        )
    if candidate["causal_claim"] is not False:
        raise RCLValidationError("Intent revision requires causal_claim=false")

    behavior_payload = profile.load("behavior.json")
    behavior = _find_behavior(behavior_payload, behavior_id)
    current_intent = behavior.get("intent")
    if not isinstance(current_intent, dict):
        raise RCLValidationError(
            f"{behavior_id}: intent revision requires an existing declared intent; use approve-intent for first attachment"
        )

    current_sha = _sha256_json(current_intent)
    if candidate["current_intent_sha256"] != current_sha:
        raise RCLValidationError(
            f"{behavior_id}: revision candidate current_intent_sha256 does not match the current profile"
        )

    replacement = candidate["replacement_intent"]
    _validate_replacement_intent(behavior, replacement)
    if _semantic_intent(current_intent) == replacement:
        raise RCLValidationError(f"{behavior_id}: replacement intent is semantically unchanged")
    return behavior, current_intent


def _revision_id(
    *,
    behavior_id: str,
    current_intent_sha256: str,
    candidate_sha256: str,
    approved_at: str,
    approved_by: str | None,
) -> str:
    material = "|".join(
        [behavior_id, current_intent_sha256, candidate_sha256, approved_at, approved_by or ""]
    )
    return "intent-revision-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def preview_intent_revision(
    profile: RCLProfile,
    revision_candidate: dict[str, Any],
    behavior_id: str,
    *,
    approved_at: str,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic correction patch without mutating the source profile."""

    behavior, current_intent = _validate_revision_candidate(profile, revision_candidate, behavior_id)
    approval_time = _parse_datetime(approved_at, label="approved_at")
    candidate_time = _parse_datetime(revision_candidate["created_at"], label="revision_candidate.created_at")
    if approval_time < candidate_time:
        raise RCLValidationError("approved_at cannot precede the revision candidate timestamp")
    latest = _latest_intent_timestamp(behavior)
    if latest is not None and approval_time < latest:
        raise RCLValidationError("approved_at cannot precede the latest declared intent approval/revision")

    candidate_sha = _sha256_json(revision_candidate)
    current_sha = _sha256_json(current_intent)
    revision_id = _revision_id(
        behavior_id=behavior_id,
        current_intent_sha256=current_sha,
        candidate_sha256=candidate_sha,
        approved_at=approved_at,
        approved_by=approved_by,
    )

    after_intent = copy.deepcopy(revision_candidate["replacement_intent"])
    after_intent["provenance"] = {
        "source": "revised",
        "revision_id": revision_id,
        "revision_candidate_id": revision_candidate["candidate_id"],
        "revision_candidate_sha256": candidate_sha,
        "previous_intent_sha256": current_sha,
        "reason": revision_candidate["reason"],
        "evidence_refs": copy.deepcopy(revision_candidate["evidence_refs"]),
        "approved_at": approved_at,
        "approved_by": approved_by,
        "causal_claim": False,
    }
    after_sha = _sha256_json(after_intent)

    history_entry = {
        "revision_id": revision_id,
        "revised_at": approved_at,
        "revised_by": approved_by,
        "candidate_id": revision_candidate["candidate_id"],
        "candidate_sha256": candidate_sha,
        "reason": revision_candidate["reason"],
        "evidence_refs": copy.deepcopy(revision_candidate["evidence_refs"]),
        "from_intent_sha256": current_sha,
        "to_intent_sha256": after_sha,
        "intent_snapshot": copy.deepcopy(current_intent),
        "causal_claim": False,
    }

    patch = {
        "revision_version": INTENT_REVISION_VERSION,
        "method": INTENT_REVISION_PATCH_METHOD,
        "behavior_id": behavior_id,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "source_profile": _profile_ref(profile),
        "source_behavior_sha256": _sha256_json(behavior),
        "candidate": {
            "candidate_id": revision_candidate["candidate_id"],
            "created_at": revision_candidate["created_at"],
            "candidate_sha256": candidate_sha,
            "reason": revision_candidate["reason"],
            "evidence_refs": copy.deepcopy(revision_candidate["evidence_refs"]),
            "causal_claim": False,
        },
        "before_intent": copy.deepcopy(current_intent),
        "after_intent": after_intent,
        "history_entry": history_entry,
    }
    validate_schema(patch, "intent-revision-patch")
    return patch


def _apply_patch_to_behavior_payload(
    behavior_payload: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(behavior_payload)
    behavior = _find_behavior(result, patch["behavior_id"])
    if _sha256_json(behavior) != patch["source_behavior_sha256"]:
        raise RCLValidationError("Intent revision patch source behavior no longer matches the profile")
    current_intent = behavior.get("intent")
    if not isinstance(current_intent, dict):
        raise RCLValidationError("Intent revision patch target no longer has an intent")
    if _sha256_json(current_intent) != patch["history_entry"]["from_intent_sha256"]:
        raise RCLValidationError("Intent revision patch current intent no longer matches the approved source")

    history = behavior.setdefault("intent_history", [])
    if any(item["revision_id"] == patch["history_entry"]["revision_id"] for item in history):
        raise RCLValidationError("Intent revision history entry already exists")
    history.append(copy.deepcopy(patch["history_entry"]))
    behavior["intent"] = copy.deepcopy(patch["after_intent"])

    validate_schema(result, "behavior")
    validate_behavior_intent_metadata(result)
    return result


def _derive_output_profile_id(profile: RCLProfile, patch: dict[str, Any]) -> str:
    identity = profile.load("identity.json")
    base = _source_profile_id(profile) or f"{identity['robot_id']}-g{identity['continuity_generation']}"
    return f"{base}-intent-rev-{_sha256_json(patch)[:12]}"


def _assert_revision_minimality(before: dict[str, Any], after: dict[str, Any]) -> None:
    before_other = copy.deepcopy(before)
    after_other = copy.deepcopy(after)
    before_history = before_other.pop("intent_history", [])
    after_history = after_other.pop("intent_history", [])
    before_other.pop("intent", None)
    after_other.pop("intent", None)
    if before_other != after_other:
        raise RCLValidationError("Intent revision changed fields outside behavior.intent/intent_history")
    if after_history[:-1] != before_history or len(after_history) != len(before_history) + 1:
        raise RCLValidationError("Intent revision must append exactly one history entry")


def apply_intent_revision(
    profile: RCLProfile,
    revision_candidate: dict[str, Any],
    behavior_id: str,
    output_dir: str | Path,
    *,
    approved_at: str,
    approved_by: str | None = None,
    output_profile_id: str | None = None,
) -> dict[str, Any]:
    """Apply an approved correction into a new validated RCL snapshot."""

    patch = preview_intent_revision(
        profile,
        revision_candidate,
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
        _assert_revision_minimality(before_behavior, after_behavior)

        diff = diff_profiles(profile, output_profile)
        if diff["summary"] != {
            "added_behaviors": 0,
            "removed_behaviors": 0,
            "modified_behaviors": 1,
        }:
            raise RCLValidationError("Intent revision produced changes outside the selected behavior")
        if len(diff["behavior_changes"]) != 1 or diff["behavior_changes"][0]["behavior_id"] != behavior_id:
            raise RCLValidationError("Intent revision diff does not match the selected behavior")
        if diff["behavior_changes"][0]["parameter_changes"]:
            raise RCLValidationError("Intent revision must not modify semantic behavior parameters")

        if _payload_hashes(profile) != before_hashes:
            raise RCLValidationError("Source profile changed while applying intent revision")

        result = {
            "revision_version": INTENT_REVISION_VERSION,
            "method": INTENT_REVISION_APPLY_METHOD,
            "created_at": approved_at,
            "behavior_id": behavior_id,
            "revision_id": patch["history_entry"]["revision_id"],
            "candidate_id": revision_candidate["candidate_id"],
            "candidate_sha256": patch["candidate"]["candidate_sha256"],
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
                "This result records an explicitly approved engineering correction into a new RCL snapshot. "
                "The previous intent remains in append-only history. It does not prove causality, subjective motivation, identity, or safety."
            ),
        }
        validate_schema(result, "intent-revision-result")
        temp.rename(output)
        return result
    except Exception:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        raise
