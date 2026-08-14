from __future__ import annotations

from typing import Any

from .profile import RCLValidationError


EXPRESSIVE_TIMING_VERSION = "0.1"
TEMPOS = ("deliberate", "relaxed", "natural", "quick")
DWELLS = ("none", "brief", "natural", "held")
TRANSITIONS = ("gentle", "smooth", "direct", "crisp")
TIMING_POLICIES = ("naturalize", "preserve_style")
LEGACY_SIGNIFICANCE = ("incidental", "recognized", "user_valued")
SOURCE_ARTIFACTS = (
    "actuator_speed_limit",
    "gearing_limit",
    "wiring_constraint",
    "controller_latency",
    "power_limit",
    "unknown_hardware_constraint",
)
SOURCE_ARTIFACT_EFFECTS = (
    "slower_than_intended",
    "delayed_start",
    "uneven_motion",
)


def _positive_ms(value: Any, *, label: str, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RCLValidationError(f"{label} must be a number")
    numeric = float(value)
    if allow_zero:
        if numeric < 0:
            raise RCLValidationError(f"{label} must be >= 0")
    elif numeric <= 0:
        raise RCLValidationError(f"{label} must be > 0")
    return int(round(numeric))


def validate_expression_temporal_style(behavior_id: str, style: dict[str, Any]) -> None:
    if style.get("tempo") not in TEMPOS:
        raise RCLValidationError(f"{behavior_id}.expression.temporal_style: invalid tempo")
    if style.get("dwell") not in DWELLS:
        raise RCLValidationError(f"{behavior_id}.expression.temporal_style: invalid dwell")
    if style.get("transition") not in TRANSITIONS:
        raise RCLValidationError(f"{behavior_id}.expression.temporal_style: invalid transition")
    if style.get("timing_policy") not in TIMING_POLICIES:
        raise RCLValidationError(f"{behavior_id}.expression.temporal_style: invalid timing_policy")
    if style.get("legacy_significance") not in LEGACY_SIGNIFICANCE:
        raise RCLValidationError(f"{behavior_id}.expression.temporal_style: invalid legacy_significance")

    if (
        style["timing_policy"] == "preserve_style"
        and style["legacy_significance"] == "incidental"
    ):
        raise RCLValidationError(
            f"{behavior_id}: preserve_style requires recognized or user_valued legacy significance"
        )

    observation = style.get("source_timing_observation")
    if observation is not None:
        if observation.get("normative") is not False:
            raise RCLValidationError(
                f"{behavior_id}: source_timing_observation must be descriptive with normative=false"
            )
        _positive_ms(
            observation["motion_duration_ms"],
            label=f"{behavior_id}.source_timing_observation.motion_duration_ms",
        )
        _positive_ms(
            observation["dwell_duration_ms"],
            label=f"{behavior_id}.source_timing_observation.dwell_duration_ms",
            allow_zero=True,
        )
        _positive_ms(
            observation["return_duration_ms"],
            label=f"{behavior_id}.source_timing_observation.return_duration_ms",
        )

    artifacts = style.get("source_artifacts", [])
    seen: set[tuple[str, str]] = set()
    for artifact in artifacts:
        artifact_name = artifact.get("artifact")
        effect = artifact.get("effect")
        if artifact_name not in SOURCE_ARTIFACTS:
            raise RCLValidationError(f"{behavior_id}: unsupported source timing artifact {artifact_name!r}")
        if effect not in SOURCE_ARTIFACT_EFFECTS:
            raise RCLValidationError(f"{behavior_id}: unsupported source timing artifact effect {effect!r}")
        key = (artifact_name, effect)
        if key in seen:
            raise RCLValidationError(f"{behavior_id}: duplicate source timing artifact {key!r}")
        seen.add(key)


def validate_behavior_expression_timing_metadata(behavior_payload: dict[str, Any]) -> None:
    for behavior in behavior_payload.get("behaviors", []):
        expression = behavior.get("expression") or {}
        style = expression.get("temporal_style")
        if style is not None:
            validate_expression_temporal_style(behavior["behavior_id"], style)


def _mapped_duration(mapping: Any, key: str, *, label: str, allow_zero: bool = False) -> int:
    if not isinstance(mapping, dict) or key not in mapping:
        raise RCLValidationError(f"{label} does not define {key!r}")
    return _positive_ms(mapping[key], label=f"{label}.{key}", allow_zero=allow_zero)


def _clamp(value: int, lower: int | None, upper: int | None) -> tuple[int, bool]:
    result = value
    changed = False
    if lower is not None and result < lower:
        result = lower
        changed = True
    if upper is not None and result > upper:
        result = upper
        changed = True
    return result, changed


def realize_temporal_style(
    style: dict[str, Any],
    timing_profile: dict[str, Any],
) -> dict[str, Any]:
    """Resolve portable temporal style into a target-specific timing plan.

    The portable style carries semantic tempo and rhythm. Concrete millisecond
    values come from the target adapter/embodiment timing profile, never from the
    source robot's observed duration. Source observations remain descriptive only.
    """

    validate_expression_temporal_style("expression", style)

    tempo = style["tempo"]
    dwell = style["dwell"]
    motion_ms = _mapped_duration(
        timing_profile.get("tempo_duration_ms"),
        tempo,
        label="target_timing.tempo_duration_ms",
    )
    dwell_ms = _mapped_duration(
        timing_profile.get("dwell_duration_ms"),
        dwell,
        label="target_timing.dwell_duration_ms",
        allow_zero=True,
    )
    return_mapping = timing_profile.get("return_duration_ms")
    if return_mapping is None:
        return_ms = motion_ms
    else:
        return_ms = _mapped_duration(
            return_mapping,
            tempo,
            label="target_timing.return_duration_ms",
        )

    min_safe = timing_profile.get("min_safe_motion_duration_ms")
    max_safe = timing_profile.get("max_safe_motion_duration_ms")
    min_safe_ms = None if min_safe is None else _positive_ms(min_safe, label="target_timing.min_safe_motion_duration_ms")
    max_safe_ms = None if max_safe is None else _positive_ms(max_safe, label="target_timing.max_safe_motion_duration_ms")
    if min_safe_ms is not None and max_safe_ms is not None and min_safe_ms > max_safe_ms:
        raise RCLValidationError("target timing minimum safe duration exceeds maximum safe duration")

    motion_ms, motion_clamped = _clamp(motion_ms, min_safe_ms, max_safe_ms)
    return_ms, return_clamped = _clamp(return_ms, min_safe_ms, max_safe_ms)

    max_dwell = timing_profile.get("max_safe_dwell_duration_ms")
    max_dwell_ms = None if max_dwell is None else _positive_ms(
        max_dwell,
        label="target_timing.max_safe_dwell_duration_ms",
        allow_zero=True,
    )
    dwell_ms, dwell_clamped = _clamp(dwell_ms, 0, max_dwell_ms)

    approximated = motion_clamped or return_clamped or dwell_clamped
    if approximated:
        status = "approximated"
        reason = "Target safety/timing bounds required approximation of the declared temporal style."
    elif style["timing_policy"] == "naturalize":
        status = "naturalized"
        reason = "Target-native timing realizes the recognizable gesture without copying source hardware delay."
    else:
        status = "preserved"
        reason = "Target-native timing preserves the explicitly significant temporal style."

    return {
        "status": status,
        "reason": reason,
        "timing_policy": style["timing_policy"],
        "semantic_style": {
            "tempo": tempo,
            "dwell": dwell,
            "transition": style["transition"],
            "legacy_significance": style["legacy_significance"],
        },
        "realized_timing": {
            "motion_duration_ms": motion_ms,
            "dwell_duration_ms": dwell_ms,
            "return_duration_ms": return_ms,
            "transition": style["transition"],
        },
        "source_artifacts": list(style.get("source_artifacts", [])),
    }
