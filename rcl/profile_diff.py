from __future__ import annotations

from typing import Any

from .profile import RCLProfile, validate_schema


PROFILE_DIFF_VERSION = "0.1"
PROFILE_DIFF_METHOD = "rcl.profile.semantic_diff.v0.1"


def _profile_ref(profile: RCLProfile) -> dict[str, Any]:
    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")
    return {
        "robot_id": identity["robot_id"],
        "continuity_generation": identity["continuity_generation"],
        "embodiment_id": embodiment["embodiment_id"],
    }


def _behavior_map(profile: RCLProfile) -> dict[str, dict[str, Any]]:
    payload = profile.load("behavior.json")
    return {item["behavior_id"]: item for item in payload["behaviors"]}


def _change(field: str, before: Any, after: Any) -> dict[str, Any]:
    if before is None and after is not None:
        change_type = "added"
    elif before is not None and after is None:
        change_type = "removed"
    else:
        change_type = "changed"
    return {
        "field": field,
        "change_type": change_type,
        "before": before,
        "after": after,
    }


def _dict_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        before_present = key in before
        after_present = key in after
        before_value = before.get(key)
        after_value = after.get(key)
        if before_present and after_present and before_value == after_value:
            continue
        changes.append(
            _change(
                key,
                before_value if before_present else None,
                after_value if after_present else None,
            )
        )
    return changes


def _get_path(item: dict[str, Any], path: str) -> Any:
    value: Any = item
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _field_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    fields = (
        "description",
        "preservation.priority",
        "preservation.mode",
        "source",
        "confidence",
        "required_capabilities",
        "evaluation",
        "habit.lifecycle",
        "habit.first_observed_at",
        "habit.stable_since",
        "habit.legacy_since",
        "habit.user_confirmed_at",
    )
    changes: list[dict[str, Any]] = []
    for field in fields:
        before_value = _get_path(before, field)
        after_value = _get_path(after, field)
        if before_value != after_value:
            changes.append(_change(field, before_value, after_value))
    return changes


def _history_events(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    habit = item.get("habit") or {}
    return {
        event["event_id"]: event
        for event in habit.get("events", [])
    }


def diff_profiles(before: RCLProfile, after: RCLProfile) -> dict[str, Any]:
    """Return a deterministic semantic diff between two validated RCL profiles."""

    before_behaviors = _behavior_map(before)
    after_behaviors = _behavior_map(after)
    changes: list[dict[str, Any]] = []
    added_count = 0
    removed_count = 0
    modified_count = 0

    for behavior_id in sorted(set(before_behaviors) | set(after_behaviors)):
        before_item = before_behaviors.get(behavior_id)
        after_item = after_behaviors.get(behavior_id)

        if before_item is None:
            added_count += 1
            changes.append(
                {
                    "behavior_id": behavior_id,
                    "change_type": "added",
                    "parameter_changes": [],
                    "field_changes": [],
                    "history_events_added": list(_history_events(after_item).values()),
                    "history_event_ids_removed": [],
                }
            )
            continue

        if after_item is None:
            removed_count += 1
            changes.append(
                {
                    "behavior_id": behavior_id,
                    "change_type": "removed",
                    "parameter_changes": [],
                    "field_changes": [],
                    "history_events_added": [],
                    "history_event_ids_removed": sorted(_history_events(before_item)),
                }
            )
            continue

        parameter_changes = _dict_changes(
            before_item.get("parameters", {}),
            after_item.get("parameters", {}),
        )
        field_changes = _field_changes(before_item, after_item)
        before_events = _history_events(before_item)
        after_events = _history_events(after_item)
        history_events_added = [
            after_events[event_id]
            for event_id in sorted(set(after_events) - set(before_events))
        ]
        history_event_ids_removed = sorted(set(before_events) - set(after_events))

        if parameter_changes or field_changes or history_events_added or history_event_ids_removed:
            modified_count += 1
            changes.append(
                {
                    "behavior_id": behavior_id,
                    "change_type": "modified",
                    "parameter_changes": parameter_changes,
                    "field_changes": field_changes,
                    "history_events_added": history_events_added,
                    "history_event_ids_removed": history_event_ids_removed,
                }
            )

    report = {
        "diff_version": PROFILE_DIFF_VERSION,
        "method": PROFILE_DIFF_METHOD,
        "before": _profile_ref(before),
        "after": _profile_ref(after),
        "changed": bool(changes),
        "summary": {
            "added_behaviors": added_count,
            "removed_behaviors": removed_count,
            "modified_behaviors": modified_count,
        },
        "behavior_changes": changes,
    }
    validate_schema(report, "profile-diff-report")
    return report
