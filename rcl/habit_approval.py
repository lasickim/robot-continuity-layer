from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .history import validate_behavior_habit_metadata
from .profile import PAYLOADS, RCLProfile, RCLValidationError, validate_schema
from .profile_diff import diff_profiles


HABIT_APPROVAL_VERSION = "0.1"
HABIT_APPROVAL_PATCH_METHOD = "rcl.habit.approval.patch.v0.1"
HABIT_APPROVAL_APPLY_METHOD = "rcl.habit.approval.apply.v0.1"

_TRANSITIONS = {
    "configured": "learning",
    "learning": "stable",
    "stable": "legacy",
}


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


def _profile_identity(profile: RCLProfile) -> tuple[dict[str, Any], dict[str, Any]]:
    return profile.load("identity.json"), profile.load("embodiment.json")


def _source_profile_id(profile: RCLProfile) -> str | None:
    manifest_path = profile.root / "manifest.json"
    if not manifest_path.exists():
        return None
    return profile.load("manifest.json")["profile_id"]


def _profile_ref(profile: RCLProfile) -> dict[str, Any]:
    identity, embodiment = _profile_identity(profile)
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


def _find_candidate_decision(
    profile: RCLProfile,
    promotion_report: dict[str, Any],
    behavior_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_schema(promotion_report, "habit-promotion-report")

    if promotion_report["profile"] != _profile_ref(profile):
        raise RCLValidationError(
            "Habit promotion report profile reference does not match the source profile"
        )

    decisions = [
        item for item in promotion_report["decisions"] if item["behavior_id"] == behavior_id
    ]
    if len(decisions) != 1:
        raise RCLValidationError(
            f"Habit promotion report must contain exactly one decision for {behavior_id}"
        )
    decision = decisions[0]
    if decision["decision"] != "candidate" or not decision["eligible"]:
        raise RCLValidationError(
            f"Habit promotion decision for {behavior_id} is not an eligible candidate"
        )
    target = decision["recommended_lifecycle"]
    if target is None:
        raise RCLValidationError(f"Habit promotion candidate {behavior_id} has no target lifecycle")

    behavior_payload = profile.load("behavior.json")
    behavior = _find_behavior(behavior_payload, behavior_id)
    habit = behavior.get("habit")
    if not isinstance(habit, dict):
        raise RCLValidationError(f"{behavior_id}: explicit approval requires habit metadata")

    current = habit["lifecycle"]
    if current != decision["current_lifecycle"]:
        raise RCLValidationError(
            f"{behavior_id}: profile lifecycle {current!r} does not match promotion report "
            f"lifecycle {decision['current_lifecycle']!r}"
        )
    expected_target = _TRANSITIONS.get(current)
    if expected_target != target:
        raise RCLValidationError(
            f"{behavior_id}: invalid lifecycle transition {current!r} -> {target!r}"
        )
    return decision, behavior


def _approval_event_id(
    *,
    behavior_id: str,
    from_lifecycle: str,
    to_lifecycle: str,
    approved_at: str,
    approved_by: str | None,
    promotion_created_at: str,
) -> str:
    material = "|".join(
        [
            behavior_id,
            from_lifecycle,
            to_lifecycle,
            approved_at,
            approved_by or "",
            promotion_created_at,
        ]
    )
    return f"approval-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def preview_habit_approval(
    profile: RCLProfile,
    promotion_report: dict[str, Any],
    behavior_id: str,
    *,
    approved_at: str,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic lifecycle approval patch without mutating the profile."""

    decision, behavior = _find_candidate_decision(profile, promotion_report, behavior_id)
    habit = behavior["habit"]
    from_lifecycle = habit["lifecycle"]
    to_lifecycle = decision["recommended_lifecycle"]
    assert to_lifecycle is not None

    approval_time = _parse_datetime(approved_at, label="approved_at")
    evidence_time = max(
        _parse_datetime(promotion_report["created_at"], label="promotion_report.created_at"),
        _parse_datetime(promotion_report["as_of"], label="promotion_report.as_of"),
    )
    if approval_time < evidence_time:
        raise RCLValidationError("approved_at cannot precede the promotion evidence timestamp")

    events = habit.get("events", [])
    if events:
        latest_event = _parse_datetime(events[-1]["observed_at"], label="habit.events[-1].observed_at")
        if approval_time < latest_event:
            raise RCLValidationError("approved_at cannot precede the latest habit history event")

    changes: list[dict[str, Any]] = [
        {
            "path": "habit.lifecycle",
            "before": from_lifecycle,
            "after": to_lifecycle,
        }
    ]

    if to_lifecycle == "stable":
        changes.append(
            {
                "path": "habit.stable_since",
                "before": habit.get("stable_since"),
                "after": approved_at,
            }
        )
        if habit.get("user_confirmed_at") is None:
            changes.append(
                {
                    "path": "habit.user_confirmed_at",
                    "before": None,
                    "after": approved_at,
                }
            )
    elif to_lifecycle == "legacy":
        changes.append(
            {
                "path": "habit.legacy_since",
                "before": habit.get("legacy_since"),
                "after": approved_at,
            }
        )
        if habit.get("user_confirmed_at") is None:
            changes.append(
                {
                    "path": "habit.user_confirmed_at",
                    "before": None,
                    "after": approved_at,
                }
            )

    policy_ref = promotion_report["policy"]
    event_id = _approval_event_id(
        behavior_id=behavior_id,
        from_lifecycle=from_lifecycle,
        to_lifecycle=to_lifecycle,
        approved_at=approved_at,
        approved_by=approved_by,
        promotion_created_at=promotion_report["created_at"],
    )
    actor_text = f" by {approved_by}" if approved_by else ""
    patch = {
        "approval_version": HABIT_APPROVAL_VERSION,
        "method": HABIT_APPROVAL_PATCH_METHOD,
        "behavior_id": behavior_id,
        "from_lifecycle": from_lifecycle,
        "to_lifecycle": to_lifecycle,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "promotion_evidence": {
            "method": promotion_report["method"],
            "created_at": promotion_report["created_at"],
            "as_of": promotion_report["as_of"],
            "policy_id": policy_ref["policy_id"],
            "policy_version": policy_ref["policy_version"],
        },
        "changes": changes,
        "history_event": {
            "event_id": event_id,
            "observed_at": approved_at,
            "event_type": "promotion_approved",
            "note": (
                f"Explicitly approved habit lifecycle transition "
                f"{from_lifecycle} -> {to_lifecycle}{actor_text}."
            ),
            "evidence_ref": (
                f"habit-promotion:{policy_ref['policy_id']}@{policy_ref['policy_version']}:"
                f"{promotion_report['created_at']}"
            ),
        },
    }
    validate_schema(patch, "habit-approval-patch")
    return patch


def _apply_patch_to_behavior_payload(
    behavior_payload: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(behavior_payload)
    behavior = _find_behavior(result, patch["behavior_id"])
    habit = behavior["habit"]
    if habit["lifecycle"] != patch["from_lifecycle"]:
        raise RCLValidationError("Approval patch source lifecycle no longer matches the profile")

    for change in patch["changes"]:
        field = change["path"].removeprefix("habit.")
        actual = habit.get(field)
        if actual != change["before"]:
            raise RCLValidationError(
                f"Approval patch precondition failed for {change['path']}: "
                f"expected {change['before']!r}, found {actual!r}"
            )
        habit[field] = change["after"]

    if any(event["event_id"] == patch["history_event"]["event_id"] for event in habit["events"]):
        raise RCLValidationError("Approval history event already exists")
    habit["events"].append(copy.deepcopy(patch["history_event"]))

    validate_schema(result, "behavior")
    validate_behavior_habit_metadata(result)
    return result


def _derive_output_profile_id(
    profile: RCLProfile,
    patch: dict[str, Any],
) -> str:
    identity = profile.load("identity.json")
    base = _source_profile_id(profile) or (
        f"{identity['robot_id']}-g{identity['continuity_generation']}"
    )
    return f"{base}-habit-{_sha256_json(patch)[:12]}"


def apply_habit_approval(
    profile: RCLProfile,
    promotion_report: dict[str, Any],
    behavior_id: str,
    output_dir: str | Path,
    *,
    approved_at: str,
    approved_by: str | None = None,
    output_profile_id: str | None = None,
) -> dict[str, Any]:
    """Apply an eligible approval to a new validated snapshot directory."""

    patch = preview_habit_approval(
        profile,
        promotion_report,
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
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=str(output.parent)))

    try:
        for payload_name in PAYLOADS:
            shutil.copyfile(profile.root / payload_name, temp / payload_name)

        behavior_payload = profile.load("behavior.json")
        updated_behavior = _apply_patch_to_behavior_payload(behavior_payload, patch)
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
        diff = diff_profiles(profile, output_profile)
        if diff["summary"] != {
            "added_behaviors": 0,
            "removed_behaviors": 0,
            "modified_behaviors": 1,
        }:
            raise RCLValidationError("Approval produced changes outside the selected behavior")
        if len(diff["behavior_changes"]) != 1 or diff["behavior_changes"][0]["behavior_id"] != behavior_id:
            raise RCLValidationError("Approval diff does not match the selected behavior")
        if diff["behavior_changes"][0]["parameter_changes"]:
            raise RCLValidationError("Habit approval must not modify semantic behavior parameters")

        after_hashes = _payload_hashes(profile)
        if before_hashes != after_hashes:
            raise RCLValidationError("Source profile changed while applying approval")

        result = {
            "approval_version": HABIT_APPROVAL_VERSION,
            "method": HABIT_APPROVAL_APPLY_METHOD,
            "created_at": approved_at,
            "behavior_id": behavior_id,
            "from_lifecycle": patch["from_lifecycle"],
            "to_lifecycle": patch["to_lifecycle"],
            "patch_sha256": _sha256_json(patch),
            "source_robot_id": profile.load("identity.json")["robot_id"],
            "source_profile_id": _source_profile_id(profile),
            "output_profile_id": new_profile_id,
            "output_path": str(output),
            "source_unchanged": True,
            "output_valid": True,
            "diff_summary": diff["summary"],
            "disclaimer": (
                "This result records an explicit lifecycle approval into a new RCL snapshot. "
                "It does not alter semantic behavior parameters, imply identity/personhood, or override safety."
            ),
        }
        validate_schema(result, "habit-approval-result")
        temp.rename(output)
        return result
    except Exception:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        raise
