from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .expression_timing import validate_expression_temporal_style
from .profile import RCLValidationError, validate_schema


NULL_EXPRESSION_SHA256 = hashlib.sha256(b"null").hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def expression_sha256(expression: dict[str, Any] | None) -> str:
    if expression is None:
        return NULL_EXPRESSION_SHA256
    return hashlib.sha256(_canonical_json(expression).encode("utf-8")).hexdigest()


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if result.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return result


def validate_expression_object(expression: dict[str, Any], *, behavior_id: str) -> None:
    synthetic = {
        "behaviors": [
            {
                "behavior_id": behavior_id,
                "parameters": {},
                "preservation": {"priority": "optional", "mode": "legacy"},
                "expression": expression,
            }
        ]
    }
    validate_schema(synthetic, "behavior")
    style = expression.get("temporal_style")
    if style is not None:
        validate_expression_temporal_style(behavior_id, style)


def validate_behavior_expression_history_metadata(behavior_payload: dict[str, Any]) -> None:
    for behavior in behavior_payload.get("behaviors", []):
        behavior_id = behavior["behavior_id"]
        current = behavior.get("expression")
        history = behavior.get("expression_history", [])
        if current is not None:
            validate_expression_object(current, behavior_id=behavior_id)
        if not history:
            continue

        seen_ids: set[str] = set()
        previous_time: datetime | None = None
        previous_to_sha: str | None = None

        for index, entry in enumerate(history):
            optimization_id = entry["optimization_id"]
            if optimization_id in seen_ids:
                raise RCLValidationError(
                    f"{behavior_id}: duplicate expression optimization_id {optimization_id}"
                )
            seen_ids.add(optimization_id)

            optimized_at = _parse_datetime(
                entry["optimized_at"],
                label=f"{behavior_id}.expression_history[{index}].optimized_at",
            )
            if previous_time is not None and optimized_at < previous_time:
                raise RCLValidationError(
                    f"{behavior_id}: expression_history must be chronological"
                )
            previous_time = optimized_at

            snapshot = entry["expression_snapshot"]
            validate_expression_object(
                snapshot,
                behavior_id=f"{behavior_id}.expression_history[{index}]",
            )
            actual_from = expression_sha256(snapshot)
            if actual_from != entry["from_expression_sha256"]:
                raise RCLValidationError(
                    f"{behavior_id}: expression_history[{index}] from_expression_sha256 does not match snapshot"
                )
            if previous_to_sha is not None and previous_to_sha != actual_from:
                raise RCLValidationError(
                    f"{behavior_id}: expression optimization digest chain is broken at index {index}"
                )
            if entry["action"] == "remove" and entry["to_expression_sha256"] != NULL_EXPRESSION_SHA256:
                raise RCLValidationError(
                    f"{behavior_id}: remove history entry must end at the null-expression digest"
                )
            previous_to_sha = entry["to_expression_sha256"]

        if previous_to_sha != expression_sha256(current):
            raise RCLValidationError(
                f"{behavior_id}: current expression does not match final expression-history digest"
            )
