from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Any

from .capabilities import validate_capability_set
from .capability_paths import validate_intent_capability_paths
from .profile import RCLValidationError, validate_schema


INTENT_VOCABULARY_VERSION = "0.1"
INTENT_VOCABULARY_RESOURCE = "intent-vocabulary-v0.1.json"

_SEGMENT = r"[a-z][a-z0-9_]*"
_OWNER = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_STANDARD_GOAL_RE = re.compile(rf"^(?P<namespace>{_SEGMENT})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")
_EXTENSION_GOAL_RE = re.compile(rf"^x\.(?P<owner>{_OWNER})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if result.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return result


@lru_cache(maxsize=1)
def load_intent_vocabulary() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", INTENT_VOCABULARY_RESOURCE)
    vocabulary = json.loads(resource.read_text(encoding="utf-8"))

    if vocabulary.get("vocabulary_id") != "rcl.behavior-intent":
        raise RCLValidationError("Unexpected intent vocabulary_id")
    if vocabulary.get("vocabulary_version") != INTENT_VOCABULARY_VERSION:
        raise RCLValidationError("Unsupported intent vocabulary version")

    goals = vocabulary.get("goals")
    if not isinstance(goals, list) or not goals:
        raise RCLValidationError("Intent vocabulary requires at least one goal")

    ids = [item.get("goal_id") for item in goals]
    if any(not isinstance(item, str) or not item for item in ids):
        raise RCLValidationError("Intent vocabulary contains an invalid goal_id")
    if len(ids) != len(set(ids)):
        raise RCLValidationError("Intent vocabulary contains duplicate goal_id values")

    for item in goals:
        goal_id = item["goal_id"]
        if _STANDARD_GOAL_RE.fullmatch(goal_id) is None:
            raise RCLValidationError(f"Registered intent goal has invalid ID: {goal_id}")
        for field in ("triggers", "success_conditions", "allowed_failure_actions"):
            values = item.get(field)
            if not isinstance(values, list) or not values:
                raise RCLValidationError(f"{goal_id}: {field} must be a non-empty list")
            if len(values) != len(set(values)):
                raise RCLValidationError(f"{goal_id}: {field} contains duplicate values")

    return vocabulary


def registered_intent_goals() -> list[dict[str, Any]]:
    return [dict(item) for item in load_intent_vocabulary()["goals"]]


def get_intent_goal(goal_id: str) -> dict[str, Any] | None:
    for item in load_intent_vocabulary()["goals"]:
        if item["goal_id"] == goal_id:
            return dict(item)
    return None


def _validate_goal_reference(goal_id: str) -> dict[str, Any] | None:
    definition = get_intent_goal(goal_id)
    if definition is not None:
        return definition
    if _EXTENSION_GOAL_RE.fullmatch(goal_id) is not None:
        return None
    if _STANDARD_GOAL_RE.fullmatch(goal_id) is not None:
        raise RCLValidationError(
            f"{goal_id}: unregistered standard intent goal in Behavior Intent vocabulary v{INTENT_VOCABULARY_VERSION}; "
            "use a registered goal or x.<owner>.<semantic_path> for an experimental extension"
        )
    raise RCLValidationError(f"Malformed intent goal_id: {goal_id}")


def _validate_intent(behavior_id: str, intent: dict[str, Any]) -> None:
    goal_id = intent["goal_id"]
    definition = _validate_goal_reference(goal_id)
    validate_intent_capability_paths(intent)

    if definition is not None:
        if intent["trigger"] not in definition["triggers"]:
            raise RCLValidationError(
                f"{behavior_id}.intent.trigger {intent['trigger']!r} is not registered for {goal_id}"
            )
        if intent["success_condition"] not in definition["success_conditions"]:
            raise RCLValidationError(
                f"{behavior_id}.intent.success_condition {intent['success_condition']!r} is not registered for {goal_id}"
            )
        if intent["failure_action"] not in definition["allowed_failure_actions"]:
            raise RCLValidationError(
                f"{behavior_id}.intent.failure_action {intent['failure_action']!r} is not allowed for {goal_id}"
            )


def _validate_history_snapshot(behavior_id: str, snapshot: dict[str, Any], index: int) -> None:
    synthetic = {
        "behaviors": [
            {
                "behavior_id": f"x.rcl.intent_history_{index}",
                "parameters": {},
                "preservation": {"priority": "optional", "mode": "semantic"},
                "intent": snapshot,
            }
        ]
    }
    validate_schema(synthetic, "behavior")
    _validate_intent(f"{behavior_id}.intent_history[{index}]", snapshot)


def _validate_revision_history(behavior_id: str, behavior: dict[str, Any]) -> None:
    history = behavior.get("intent_history", [])
    intent = behavior.get("intent")
    if not history:
        provenance = (intent or {}).get("provenance") if isinstance(intent, dict) else None
        if isinstance(provenance, dict) and provenance.get("source") == "revised":
            raise RCLValidationError(f"{behavior_id}: revised intent requires intent_history")
        return
    if intent is None:
        raise RCLValidationError(f"{behavior_id}: intent_history requires a current intent")

    revision_ids: set[str] = set()
    previous_time: datetime | None = None
    previous_to_sha: str | None = None

    for index, entry in enumerate(history):
        revision_id = entry["revision_id"]
        if revision_id in revision_ids:
            raise RCLValidationError(f"{behavior_id}: duplicate intent revision_id {revision_id}")
        revision_ids.add(revision_id)

        revised_at = _parse_datetime(entry["revised_at"], label=f"{behavior_id}.intent_history[{index}].revised_at")
        if previous_time is not None and revised_at < previous_time:
            raise RCLValidationError(f"{behavior_id}: intent_history must be chronological")
        previous_time = revised_at

        snapshot = entry["intent_snapshot"]
        _validate_history_snapshot(behavior_id, snapshot, index)
        actual_from_sha = _sha256_json(snapshot)
        if actual_from_sha != entry["from_intent_sha256"]:
            raise RCLValidationError(
                f"{behavior_id}: intent_history[{index}] from_intent_sha256 does not match snapshot"
            )
        if previous_to_sha is not None and previous_to_sha != entry["from_intent_sha256"]:
            raise RCLValidationError(f"{behavior_id}: intent revision digest chain is broken at index {index}")
        previous_to_sha = entry["to_intent_sha256"]

    current_sha = _sha256_json(intent)
    if previous_to_sha != current_sha:
        raise RCLValidationError(f"{behavior_id}: current intent does not match final revision digest")

    provenance = intent.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("source") != "revised":
        raise RCLValidationError(f"{behavior_id}: intent_history requires revised current-intent provenance")
    last = history[-1]
    if provenance["revision_id"] != last["revision_id"]:
        raise RCLValidationError(f"{behavior_id}: current provenance revision_id does not match history")
    if provenance["revision_candidate_id"] != last["candidate_id"]:
        raise RCLValidationError(f"{behavior_id}: current provenance candidate_id does not match history")
    if provenance["revision_candidate_sha256"] != last["candidate_sha256"]:
        raise RCLValidationError(f"{behavior_id}: current provenance candidate digest does not match history")
    if provenance["previous_intent_sha256"] != last["from_intent_sha256"]:
        raise RCLValidationError(f"{behavior_id}: current provenance previous_intent_sha256 does not match history")
    if provenance["approved_at"] != last["revised_at"]:
        raise RCLValidationError(f"{behavior_id}: current provenance approved_at does not match history")
    if provenance["reason"] != last["reason"] or provenance["evidence_refs"] != last["evidence_refs"]:
        raise RCLValidationError(f"{behavior_id}: current provenance reason/evidence does not match history")


def validate_behavior_intent_metadata(behavior_payload: dict[str, Any]) -> None:
    """Validate semantic intent, revision history, and visible-expression metadata."""

    for behavior in behavior_payload.get("behaviors", []):
        behavior_id = behavior["behavior_id"]
        intent = behavior.get("intent")
        if intent is not None:
            _validate_intent(behavior_id, intent)

        _validate_revision_history(behavior_id, behavior)

        expression = behavior.get("expression")
        if expression is not None:
            validate_capability_set(expression["required_capabilities"])
            if intent is None and behavior.get("preservation", {}).get("mode") != "legacy":
                raise RCLValidationError(
                    f"{behavior_id}: expression without intent is only valid for a legacy behavior"
                )
