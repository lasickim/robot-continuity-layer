from __future__ import annotations

from datetime import datetime, timezone
from math import isclose
from typing import Any

from .capability_manifest import preferred_support_for_dimension, validate_capability_manifest
from .continuity_profile import signature_for_behavior, trait_index, validate_continuity_profile
from .identity_constraint import validate_constraints_against_profile
from .profile import RCLValidationError, validate_schema


COMPATIBILITY_MAPPING_VERSION = "0.1"
CLASSIFICATIONS = ("EXACT", "APPROXIMATE", "SUBSTITUTE", "UNSUPPORTED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _value_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "unknown"


def _within_tolerance(source: float, target: float, tolerance: dict[str, Any]) -> bool:
    error = abs(target - source)
    mode = tolerance["mode"]
    if mode == "exact":
        return isclose(error, 0.0, abs_tol=1e-9)
    if mode == "absolute":
        return error <= float(tolerance["value"]) + 1e-9
    if mode == "relative":
        if isclose(source, 0.0, abs_tol=1e-12):
            return isclose(error, 0.0, abs_tol=1e-9)
        return error / abs(source) <= float(tolerance["value"]) + 1e-9
    raise RCLValidationError(f"Unsupported tolerance mode: {mode}")


def _nearest_numeric_value(source: float, support: dict[str, Any]) -> float:
    target = source
    if "minimum" in support:
        target = max(target, float(support["minimum"]))
    if "maximum" in support:
        target = min(target, float(support["maximum"]))

    resolution = support.get("resolution")
    if resolution is not None and float(resolution) > 0:
        step = float(resolution)
        origin = float(support.get("minimum", 0.0))
        target = origin + round((target - origin) / step) * step
        if "minimum" in support:
            target = max(target, float(support["minimum"]))
        if "maximum" in support:
            target = min(target, float(support["maximum"]))
    return target


def _direct_result(
    trait: dict[str, Any], support_record: dict[str, Any], constraint: dict[str, Any]
) -> dict[str, Any]:
    support = support_record["support"]
    source_value = trait["value"]
    source_kind = _value_kind(source_value)
    target_kind = support["value_kind"]

    if target_kind == "categorical":
        if not isinstance(source_value, str):
            return _unsupported("value_kind_mismatch", support_record)
        if source_value not in support["allowed_values"]:
            return _unsupported("categorical_value_not_supported", support_record)
        return _exact(source_value, support_record)

    if source_kind != target_kind:
        return _unsupported("value_kind_mismatch", support_record)

    if target_kind == "number":
        source_unit = trait.get("unit")
        target_unit = support.get("unit")
        if source_unit != target_unit:
            return _unsupported("unit_mismatch", support_record)
        source_number = float(source_value)
        target_number = _nearest_numeric_value(source_number, support)
        exact = isclose(source_number, target_number, abs_tol=1e-9)
        return {
            "classification": "EXACT" if exact else "APPROXIMATE",
            "constraint_satisfied": _within_tolerance(
                source_number, target_number, constraint["tolerance"]
            ),
            "reason": "direct_exact" if exact else "nearest_reachable_value",
            "capability_id": support_record["capability_id"],
            "mapping_mode": "direct",
            "source_value": source_value,
            "target_value": target_number,
            "absolute_error": abs(target_number - source_number),
        }

    return _exact(source_value, support_record)


def _exact(value: Any, support_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "classification": "EXACT",
        "constraint_satisfied": True,
        "reason": "direct_exact",
        "capability_id": support_record["capability_id"],
        "mapping_mode": "direct",
        "source_value": value,
        "target_value": value,
    }


def _unsupported(reason: str, support_record: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "classification": "UNSUPPORTED",
        "constraint_satisfied": False,
        "reason": reason,
    }
    if support_record is not None:
        result["capability_id"] = support_record["capability_id"]
        result["mapping_mode"] = support_record["support"]["mapping_mode"]
    return result


def map_behavioral_compatibility(
    profile: dict[str, Any],
    constraints: dict[str, Any],
    target_manifest: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Map observed source identity traits onto one target embodiment.

    Classification describes the physical/semantic mapping route. The separate
    constraint_satisfied flag says whether that route is acceptable under the
    source identity preservation policy. Continuity scoring is intentionally a
    later layer.
    """

    validate_continuity_profile(profile)
    validate_constraints_against_profile(constraints, profile)
    validate_capability_manifest(target_manifest)

    mappings: list[dict[str, Any]] = []
    for constraint in constraints["constraints"]:
        signature = signature_for_behavior(
            profile,
            constraint["behavior_id"],
            context=constraint.get("context"),
        )
        trait = trait_index(signature)[constraint["dimension"]]
        support_record = preferred_support_for_dimension(
            target_manifest, constraint["dimension"]
        )

        if support_record is None:
            result = _unsupported("no_target_support")
        elif support_record["support"]["mapping_mode"] == "substitute":
            if constraint["substitution_allowed"]:
                result = {
                    "classification": "SUBSTITUTE",
                    "constraint_satisfied": True,
                    "reason": "approved_substitution",
                    "capability_id": support_record["capability_id"],
                    "mapping_mode": "substitute",
                    "source_value": trait["value"],
                    "substitution_strategy": support_record["support"][
                        "substitution_strategy"
                    ],
                }
            else:
                result = _unsupported("substitution_forbidden", support_record)
        else:
            result = _direct_result(trait, support_record, constraint)

        mappings.append(
            {
                "constraint_id": constraint["constraint_id"],
                "behavior_id": constraint["behavior_id"],
                "dimension": constraint["dimension"],
                "importance": constraint["importance"],
                "preservation_mode": constraint["preservation_mode"],
                **result,
            }
        )

    counts = {name: sum(1 for item in mappings if item["classification"] == name) for name in CLASSIFICATIONS}
    report = {
        "compatibility_mapping_version": COMPATIBILITY_MAPPING_VERSION,
        "created_at": created_at or _now(),
        "source_robot_id": profile["robot_id"],
        "source_profile_id": profile["profile_id"],
        "constraint_set_id": constraints["constraint_set_id"],
        "target_robot_id": target_manifest["robot_id"],
        "target_embodiment_id": target_manifest["embodiment_id"],
        "mappings": mappings,
        "summary": {
            "trait_count": len(mappings),
            "counts": counts,
            "all_constraints_satisfied": all(
                item["constraint_satisfied"] for item in mappings
            ),
        },
    }
    validate_schema(report, "compatibility-mapping-report")
    return report
