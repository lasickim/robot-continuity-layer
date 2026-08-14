from __future__ import annotations

from datetime import datetime
from typing import Any

from .profile import RCLValidationError


HABIT_LIFECYCLES = ("configured", "learning", "stable", "legacy")


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc


def validate_behavior_habit_metadata(behavior_payload: dict[str, Any]) -> None:
    """Validate cross-field habit/history rules not expressible in JSON Schema.

    History is descriptive only. The current canonical behavior values remain in
    ``behavior.parameters``; events never mutate the profile while validating.
    """

    behavior_ids: set[str] = set()
    for behavior in behavior_payload.get("behaviors", []):
        behavior_id = behavior["behavior_id"]
        if behavior_id in behavior_ids:
            raise RCLValidationError(f"Duplicate behavior_id: {behavior_id}")
        behavior_ids.add(behavior_id)

        habit = behavior.get("habit")
        if habit is None:
            continue

        lifecycle = habit["lifecycle"]
        first = _parse_datetime(
            habit["first_observed_at"],
            label=f"{behavior_id}.habit.first_observed_at",
        )

        stable_value = habit.get("stable_since")
        legacy_value = habit.get("legacy_since")
        confirmed_value = habit.get("user_confirmed_at")
        stable = (
            _parse_datetime(stable_value, label=f"{behavior_id}.habit.stable_since")
            if stable_value is not None
            else None
        )
        legacy = (
            _parse_datetime(legacy_value, label=f"{behavior_id}.habit.legacy_since")
            if legacy_value is not None
            else None
        )
        confirmed = (
            _parse_datetime(
                confirmed_value,
                label=f"{behavior_id}.habit.user_confirmed_at",
            )
            if confirmed_value is not None
            else None
        )

        if lifecycle in {"stable", "legacy"} and stable is None:
            raise RCLValidationError(
                f"{behavior_id}: lifecycle {lifecycle!r} requires stable_since"
            )
        if lifecycle == "legacy" and legacy is None:
            raise RCLValidationError(
                f"{behavior_id}: lifecycle 'legacy' requires legacy_since"
            )
        if stable is not None and stable < first:
            raise RCLValidationError(
                f"{behavior_id}: stable_since cannot precede first_observed_at"
            )
        if legacy is not None:
            baseline = stable if stable is not None else first
            if legacy < baseline:
                raise RCLValidationError(
                    f"{behavior_id}: legacy_since cannot precede stable history"
                )
        if confirmed is not None and confirmed < first:
            raise RCLValidationError(
                f"{behavior_id}: user_confirmed_at cannot precede first_observed_at"
            )

        event_ids: set[str] = set()
        previous_time: datetime | None = None
        for event in habit["events"]:
            event_id = event["event_id"]
            if event_id in event_ids:
                raise RCLValidationError(
                    f"{behavior_id}: duplicate habit event_id {event_id!r}"
                )
            event_ids.add(event_id)

            observed = _parse_datetime(
                event["observed_at"],
                label=f"{behavior_id}.habit.events.{event_id}.observed_at",
            )
            if observed < first:
                raise RCLValidationError(
                    f"{behavior_id}.{event_id}: event cannot precede first_observed_at"
                )
            if previous_time is not None and observed < previous_time:
                raise RCLValidationError(
                    f"{behavior_id}: habit events must be chronological"
                )
            previous_time = observed
