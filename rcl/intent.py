from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any

from .capabilities import validate_capability_set
from .profile import RCLValidationError


INTENT_VOCABULARY_VERSION = "0.1"
INTENT_VOCABULARY_RESOURCE = "intent-vocabulary-v0.1.json"

_SEGMENT = r"[a-z][a-z0-9_]*"
_OWNER = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_STANDARD_GOAL_RE = re.compile(rf"^(?P<namespace>{_SEGMENT})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")
_EXTENSION_GOAL_RE = re.compile(rf"^x\.(?P<owner>{_OWNER})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")


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


def validate_behavior_intent_metadata(behavior_payload: dict[str, Any]) -> None:
    """Validate semantic intent and visible-expression metadata.

    Intent describes the portable purpose and success condition. Expression is a
    separately preserved visible/historical behavior and never substitutes for
    satisfying a required intent.
    """

    for behavior in behavior_payload.get("behaviors", []):
        behavior_id = behavior["behavior_id"]
        intent = behavior.get("intent")
        if intent is not None:
            goal_id = intent["goal_id"]
            definition = _validate_goal_reference(goal_id)
            validate_capability_set(intent["required_capabilities"])

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

        expression = behavior.get("expression")
        if expression is not None:
            validate_capability_set(expression["required_capabilities"])
            if intent is None and behavior.get("preservation", {}).get("mode") != "legacy":
                raise RCLValidationError(
                    f"{behavior_id}: expression without intent is only valid for a legacy behavior"
                )
