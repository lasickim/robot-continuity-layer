from __future__ import annotations

from typing import Any

from .profile import RCLValidationError, validate_schema


CONTINUITY_PROFILE_VERSION = "0.1"
BEHAVIORAL_SIGNATURE_VERSION = "0.1"


def validate_behavioral_signature(signature: dict[str, Any]) -> None:
    """Validate one observed behavioral identity signature.

    A signature describes what was observed about a robot's manner of performing
    a behavior. Identity importance and migration policy are intentionally not
    encoded here; those belong to the IdentityConstraint layer.
    """

    validate_schema(signature, "behavioral-signature")
    seen_trait_ids: set[str] = set()
    seen_dimensions: set[str] = set()
    for trait in signature["traits"]:
        trait_id = trait["trait_id"]
        dimension = trait["dimension"]
        if trait_id in seen_trait_ids:
            raise RCLValidationError(f"Duplicate behavioral trait_id: {trait_id}")
        if dimension in seen_dimensions:
            raise RCLValidationError(
                f"Duplicate behavioral dimension in one signature: {dimension}"
            )
        seen_trait_ids.add(trait_id)
        seen_dimensions.add(dimension)


def validate_continuity_profile(profile: dict[str, Any]) -> None:
    """Validate a continuity profile and its embedded behavioral signatures."""

    validate_schema(profile, "continuity-profile")
    seen_signature_ids: set[str] = set()
    for signature in profile["signatures"]:
        validate_behavioral_signature(signature)
        signature_id = signature["signature_id"]
        if signature_id in seen_signature_ids:
            raise RCLValidationError(f"Duplicate behavioral signature_id: {signature_id}")
        seen_signature_ids.add(signature_id)


def signature_for_behavior(
    profile: dict[str, Any],
    behavior_id: str,
    *,
    context: dict[str, str | int | float | bool] | None = None,
) -> dict[str, Any]:
    """Return exactly one signature matching a behavior and optional context.

    Context matching is exact for the fields supplied by the caller. This keeps
    v0.1 deterministic while allowing later context-specific signatures without
    silently selecting between ambiguous candidates.
    """

    validate_continuity_profile(profile)
    candidates = [
        signature
        for signature in profile["signatures"]
        if signature["behavior_id"] == behavior_id
    ]
    if context is not None:
        candidates = [
            signature
            for signature in candidates
            if all(signature.get("context", {}).get(k) == v for k, v in context.items())
        ]
    if len(candidates) != 1:
        raise RCLValidationError(
            f"Expected exactly one BehavioralSignature for {behavior_id!r}; found {len(candidates)}"
        )
    return candidates[0]


def trait_index(signature: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index a signature's observed traits by semantic dimension."""

    validate_behavioral_signature(signature)
    return {trait["dimension"]: trait for trait in signature["traits"]}


def continuity_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, deterministic overview for tooling and diagnostics."""

    validate_continuity_profile(profile)
    dimensions = sorted(
        {
            trait["dimension"]
            for signature in profile["signatures"]
            for trait in signature["traits"]
        }
    )
    return {
        "continuity_profile_version": profile["continuity_profile_version"],
        "profile_id": profile["profile_id"],
        "robot_id": profile["robot_id"],
        "signature_count": len(profile["signatures"]),
        "trait_count": sum(len(s["traits"]) for s in profile["signatures"]),
        "behavior_ids": sorted({s["behavior_id"] for s in profile["signatures"]}),
        "dimensions": dimensions,
    }
