from __future__ import annotations

from typing import Any

from .adapter import (
    BehaviorMigrationResult,
    ExpressionMigrationResult,
    ExpressionTimingMigrationResult,
    IntentMigrationResult,
    RCLAdapter,
)
from .expression_timing import realize_temporal_style


class IntentReferenceAdapter(RCLAdapter):
    """Reference v0.4 adapter demonstrating goal and expressive continuity.

    Functional goals use target-native capabilities. Historical visible
    expressions can still be retained separately, and optional temporal style is
    realized using target-native timing rather than source actuator limitations.
    """

    adapter_id = "rcl.reference.intent"
    adapter_version = "0.4-dev"

    def supports(self, target_embodiment: dict[str, Any]) -> bool:
        return target_embodiment.get("class") in {"humanoid", "mobile_manipulator", "other"}

    def required_capabilities(self, behavior: dict[str, Any]) -> set[str]:
        required = super().required_capabilities(behavior)
        required |= self.intent_required_capabilities(behavior)
        return required

    def translate_behavior(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> BehaviorMigrationResult:
        behavior_id = behavior["behavior_id"]
        required = self.required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available

        if missing:
            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="unsupported",
                similarity=0.0,
                reason="Target cannot satisfy the functional semantic capabilities required by this behavior.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )

        if behavior_id == "safety.pre_sit_clearance_check":
            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="preserved",
                similarity=1.0,
                reason="Pre-sit clearance behavior remains functionally representable on the target.",
                mapped_parameters={
                    "precondition": "state.sitting_area_clear",
                    "failure_action": behavior["intent"]["failure_action"],
                },
                required_capabilities=tuple(sorted(required)),
            )

        if behavior_id == "interaction.present_handover":
            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="preserved",
                similarity=1.0,
                reason="Handover presentation remains functionally representable on the target.",
                mapped_parameters={
                    "success_condition": "state.handover_orientation_acceptable",
                    "release_delay_ms": behavior.get("parameters", {}).get("release_delay_ms", 0),
                },
                required_capabilities=tuple(sorted(required)),
            )

        return BehaviorMigrationResult(
            behavior_id=behavior_id,
            status="unsupported",
            similarity=0.0,
            reason="Intent reference adapter does not implement this behavior namespace.",
            required_capabilities=tuple(sorted(required)),
        )

    def translate_intent(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> IntentMigrationResult | None:
        intent = behavior.get("intent")
        if intent is None:
            return None

        required = self.intent_required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="unsupported",
                reason="Target lacks a semantic capability required to satisfy the intent.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )

        if intent["goal_id"] == "safety.verify_sitting_area_clear":
            sensors = set(target_embodiment.get("sensors", []))
            strategy = (
                "direct_rear_clearance_sensing"
                if "rear_depth_camera" in sensors or "rear_range_sensor" in sensors
                else "target_native_sitting_area_clearance"
            )
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="preserved",
                reason=(
                    "Target can verify the sitting area directly; reproducing the source robot's "
                    "rearward-looking motion is not required for function, but may remain as a legacy expression."
                ),
                target_strategy=strategy,
                required_capabilities=tuple(sorted(required)),
            )

        if intent["goal_id"] == "interaction.optimize_handover_orientation":
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="preserved",
                reason="Target can satisfy the handover-orientation goal with target-native kinematics.",
                target_strategy="target_native_handover_orientation",
                required_capabilities=tuple(sorted(required)),
            )

        return super().translate_intent(behavior, source_embodiment, target_embodiment)

    def translate_expression(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> ExpressionMigrationResult | None:
        expression = behavior.get("expression")
        if expression is None:
            return None

        required = self.expression_required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return ExpressionMigrationResult(
                expression_id=expression["expression_id"],
                status="unsupported",
                reason=(
                    "The functional goal can still be preserved, but this target lacks the "
                    "capability needed to reproduce the source robot's visible legacy expression."
                ),
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )

        return ExpressionMigrationResult(
            expression_id=expression["expression_id"],
            status="preserved",
            reason="Target can reproduce the historical visible expression separately from the goal.",
            target_expression=expression["expression_id"],
            required_capabilities=tuple(sorted(required)),
        )

    def translate_expression_timing(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> ExpressionTimingMigrationResult | None:
        expression = behavior.get("expression")
        style = (expression or {}).get("temporal_style")
        if expression is None or style is None:
            return None

        required = self.expression_required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return super().translate_expression_timing(
                behavior,
                source_embodiment,
                target_embodiment,
            )

        profiles = (
            target_embodiment.get("limits", {})
            .get("expression_timing_profiles", {})
        )
        timing_profile = profiles.get(expression["expression_id"])
        semantic_style = {
            "tempo": style["tempo"],
            "dwell": style["dwell"],
            "transition": style["transition"],
            "legacy_significance": style["legacy_significance"],
        }
        if timing_profile is None:
            return ExpressionTimingMigrationResult(
                expression_id=expression["expression_id"],
                status="unsupported",
                reason="Target has no timing profile for this legacy expression.",
                timing_policy=style["timing_policy"],
                semantic_style=semantic_style,
                source_artifacts=tuple(style.get("source_artifacts", [])),
            )

        if timing_profile.get("blocked_for_safety") is True:
            return ExpressionTimingMigrationResult(
                expression_id=expression["expression_id"],
                status="blocked_for_safety",
                reason="Target timing profile explicitly blocks this expression timing for safety.",
                timing_policy=style["timing_policy"],
                semantic_style=semantic_style,
                source_artifacts=tuple(style.get("source_artifacts", [])),
            )

        realized = realize_temporal_style(style, timing_profile)
        return ExpressionTimingMigrationResult(
            expression_id=expression["expression_id"],
            status=realized["status"],
            reason=realized["reason"],
            timing_policy=realized["timing_policy"],
            semantic_style=realized["semantic_style"],
            realized_timing=realized["realized_timing"],
            source_artifacts=tuple(realized["source_artifacts"]),
        )
