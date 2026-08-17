from __future__ import annotations

from typing import Any

from .continuity_profile import signature_for_behavior, trait_index, validate_continuity_profile
from .profile import RCLValidationError, validate_schema

IDENTITY_CONSTRAINT_VERSION = "0.1"


def validate_identity_constraints(data: dict[str, Any]) -> None:
    validate_schema(data, "identity-constraint")
    seen_ids: set[str] = set()
    seen_keys: set[tuple[Any, ...]] = set()
    for item in data["constraints"]:
        cid = item["constraint_id"]
        if cid in seen_ids:
            raise RCLValidationError(f"Duplicate identity constraint_id: {cid}")
        seen_ids.add(cid)
        key = (
            item["behavior_id"],
            item["dimension"],
            tuple(sorted(item.get("context", {}).items())),
        )
        if key in seen_keys:
            raise RCLValidationError("Duplicate identity constraint target")
        seen_keys.add(key)
        tolerance = item["tolerance"]
        mode = tolerance["mode"]
        has_value = "value" in tolerance
        if mode == "exact" and has_value:
            raise RCLValidationError("exact tolerance must not declare a value")
        if mode in {"absolute", "relative"} and not has_value:
            raise RCLValidationError(f"{mode} tolerance requires a value")
        if mode == "relative" and tolerance["value"] > 1:
            raise RCLValidationError("relative tolerance value must be <= 1")


def validate_constraints_against_profile(
    constraints: dict[str, Any], profile: dict[str, Any]
) -> None:
    validate_identity_constraints(constraints)
    validate_continuity_profile(profile)
    if constraints["robot_id"] != profile["robot_id"]:
        raise RCLValidationError("robot_id mismatch between constraints and profile")
    for item in constraints["constraints"]:
        signature = signature_for_behavior(
            profile,
            item["behavior_id"],
            context=item.get("context"),
        )
        if item["dimension"] not in trait_index(signature):
            raise RCLValidationError(
                f"Constraint references missing trait dimension: {item['dimension']}"
            )


def constraint_for_trait(
    data: dict[str, Any],
    behavior_id: str,
    dimension: str,
    *,
    context: dict[str, str | int | float | bool] | None = None,
) -> dict[str, Any]:
    validate_identity_constraints(data)
    candidates = [
        item
        for item in data["constraints"]
        if item["behavior_id"] == behavior_id and item["dimension"] == dimension
    ]
    if context is not None:
        candidates = [
            item
            for item in candidates
            if all(item.get("context", {}).get(k) == v for k, v in context.items())
        ]
    if len(candidates) != 1:
        raise RCLValidationError(
            f"Expected one constraint for {behavior_id}/{dimension}; found {len(candidates)}"
        )
    return candidates[0]


def identity_constraint_summary(data: dict[str, Any]) -> dict[str, Any]:
    validate_identity_constraints(data)
    items = data["constraints"]
    return {
        "identity_constraint_version": data["identity_constraint_version"],
        "constraint_set_id": data["constraint_set_id"],
        "robot_id": data["robot_id"],
        "constraint_count": len(items),
        "identity_critical_count": sum(
            1 for item in items if item["preservation_mode"] == "identity_critical"
        ),
        "mean_importance": sum(float(item["importance"]) for item in items) / len(items),
    }
