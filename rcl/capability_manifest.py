from __future__ import annotations

from typing import Any

from .profile import RCLValidationError, validate_schema


CAPABILITY_MANIFEST_VERSION = "0.1"


def validate_capability_manifest(manifest: dict[str, Any]) -> None:
    validate_schema(manifest, "capability-manifest")

    seen_capability_ids: set[str] = set()
    seen_support_keys: set[tuple[str, str, str]] = set()

    for capability in manifest["capabilities"]:
        capability_id = capability["capability_id"]
        if capability_id in seen_capability_ids:
            raise RCLValidationError(f"Duplicate capability_id: {capability_id}")
        seen_capability_ids.add(capability_id)

        for support in capability["supports"]:
            key = (capability_id, support["dimension"], support["mapping_mode"])
            if key in seen_support_keys:
                raise RCLValidationError(
                    f"Duplicate support declaration: {capability_id}/{support['dimension']}/{support['mapping_mode']}"
                )
            seen_support_keys.add(key)
            _validate_support_contract(support)


def _validate_support_contract(support: dict[str, Any]) -> None:
    value_kind = support["value_kind"]
    mapping_mode = support["mapping_mode"]

    if mapping_mode == "substitute" and not support.get("substitution_strategy"):
        raise RCLValidationError("substitute support requires substitution_strategy")
    if mapping_mode == "direct" and "substitution_strategy" in support:
        raise RCLValidationError("direct support must not declare substitution_strategy")

    if value_kind == "number":
        if "allowed_values" in support:
            raise RCLValidationError("numeric support must not declare allowed_values")
        if "minimum" in support and "maximum" in support and support["minimum"] > support["maximum"]:
            raise RCLValidationError("numeric support minimum must be <= maximum")
    else:
        for field in ("minimum", "maximum", "resolution", "unit"):
            if field in support:
                raise RCLValidationError(f"{value_kind} support must not declare {field}")
        if value_kind == "categorical" and "allowed_values" not in support:
            raise RCLValidationError("categorical support requires allowed_values")


def supports_for_dimension(
    manifest: dict[str, Any], dimension: str, *, mapping_mode: str | None = None
) -> list[dict[str, Any]]:
    validate_capability_manifest(manifest)
    results: list[dict[str, Any]] = []
    for capability in manifest["capabilities"]:
        for support in capability["supports"]:
            if support["dimension"] != dimension:
                continue
            if mapping_mode is not None and support["mapping_mode"] != mapping_mode:
                continue
            results.append(
                {
                    "capability_id": capability["capability_id"],
                    "category": capability["category"],
                    "support": support,
                }
            )
    return results


def preferred_support_for_dimension(
    manifest: dict[str, Any], dimension: str
) -> dict[str, Any] | None:
    """Return a deterministic direct support when available, otherwise substitute."""

    direct = supports_for_dimension(manifest, dimension, mapping_mode="direct")
    if direct:
        return sorted(direct, key=lambda item: item["capability_id"])[0]
    substitutes = supports_for_dimension(manifest, dimension, mapping_mode="substitute")
    if substitutes:
        return sorted(substitutes, key=lambda item: item["capability_id"])[0]
    return None


def capability_manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_capability_manifest(manifest)
    direct_dimensions: set[str] = set()
    substitute_dimensions: set[str] = set()
    for capability in manifest["capabilities"]:
        for support in capability["supports"]:
            target = direct_dimensions if support["mapping_mode"] == "direct" else substitute_dimensions
            target.add(support["dimension"])
    return {
        "capability_manifest_version": manifest["capability_manifest_version"],
        "manifest_id": manifest["manifest_id"],
        "robot_id": manifest["robot_id"],
        "embodiment_id": manifest["embodiment_id"],
        "capability_count": len(manifest["capabilities"]),
        "direct_dimensions": sorted(direct_dimensions),
        "substitute_dimensions": sorted(substitute_dimensions),
    }
