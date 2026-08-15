from __future__ import annotations

from typing import Any

from .adapter import BehaviorMigrationResult, IntentMigrationResult, RCLAdapter


class CapabilityPathReferenceAdapter(RCLAdapter):
    """Reference adapter for alternative Intent capability satisfaction paths."""

    adapter_id = "rcl.reference.capability_paths"
    adapter_version = "0.4-dev"

    def supports(self, target_embodiment: dict[str, Any]) -> bool:
        return target_embodiment.get("class") in {"humanoid", "mobile_manipulator", "other"}

    def translate_behavior(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> BehaviorMigrationResult:
        required = self.required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return BehaviorMigrationResult(
                behavior_id=behavior["behavior_id"],
                status="unsupported",
                similarity=0.0,
                reason="Target lacks behavior-level semantic capabilities.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )
        return BehaviorMigrationResult(
            behavior_id=behavior["behavior_id"],
            status="preserved",
            similarity=1.0,
            reason="Behavior-level semantics are representable; Intent capability paths are evaluated separately.",
            required_capabilities=tuple(sorted(required)),
        )

    def preferred_intent_capability_paths(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> tuple[str, ...]:
        available = set(target_embodiment.get("capabilities", []))
        if "x.demo.external_seat_clearance" in available:
            return ("external_seat_state", "direct_clearance", "rear_attention_classifier")
        if "perception.sitting_area_clearance" in available:
            return ("direct_clearance", "rear_attention_classifier", "external_seat_state")
        return ("rear_attention_classifier", "direct_clearance", "external_seat_state")

    def translate_intent(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> IntentMigrationResult | None:
        base = super().translate_intent(behavior, source_embodiment, target_embodiment)
        if base is None or base.status != "preserved":
            return base

        path_id = base.selected_capability_path_id
        strategy_by_path = {
            "direct_clearance": "target.direct_clearance_state",
            "rear_attention_classifier": "target.rear_attention_clearance",
            "external_seat_state": "target.external_seat_clearance",
            "legacy.required_capabilities": "target.legacy_capability_strategy",
        }
        strategy = strategy_by_path.get(path_id, f"target.capability_path.{path_id}")
        return IntentMigrationResult(
            goal_id=base.goal_id,
            status=base.status,
            reason=f"Target satisfies capability path {path_id!r} using an embodiment-specific strategy.",
            target_strategy=strategy,
            required_capabilities=base.required_capabilities,
            missing_capabilities=base.missing_capabilities,
            selected_capability_path_id=base.selected_capability_path_id,
            capability_path_results=base.capability_path_results,
        )
