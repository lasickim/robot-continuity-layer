from __future__ import annotations

from typing import Any

from .adapter import BehaviorMigrationResult, RCLAdapter


class ExampleMobileBaseAdapter(RCLAdapter):
    """Reference adapter used only for the RCL v0.2 demo."""

    adapter_id = "rcl.example.mobile_base"
    adapter_version = "0.2"

    def supports(self, target_embodiment: dict[str, Any]) -> bool:
        return target_embodiment.get("class") == "mobile_base"

    def required_capabilities(self, behavior: dict[str, Any]) -> set[str]:
        required = super().required_capabilities(behavior)
        behavior_id = behavior["behavior_id"]
        if behavior_id == "navigation.follow_person":
            required |= {
                "navigation.planar_velocity",
                "perception.person_tracking",
            }
        elif behavior_id == "navigation.pre_turn_observation":
            required |= {"perception.directional_attention"}
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
        params = behavior.get("parameters", {})
        limits = target_embodiment.get("limits", {})

        if behavior_id == "navigation.follow_person":
            if missing:
                return BehaviorMigrationResult(
                    behavior_id=behavior_id,
                    status="unsupported",
                    similarity=0.0,
                    reason="Target lacks person-following capabilities.",
                    required_capabilities=tuple(sorted(required)),
                    missing_capabilities=tuple(sorted(missing)),
                )

            style_fraction = {
                "gentle": 0.35,
                "normal": 0.55,
                "brisk": 0.75,
            }.get(params.get("speed_style"), 0.55)
            max_linear = float(limits.get("max_linear_speed_mps", 1.0))
            max_angular = float(limits.get("max_angular_speed_rps", 1.0))
            turn_fraction = 0.45 if params.get("turn_style") == "cautious" else 0.7
            mapped = {
                "following_distance_m": params.get("preferred_distance_m", 1.0),
                "linear_speed_limit_mps": round(max_linear * style_fraction, 3),
                "angular_speed_limit_rps": round(max_angular * turn_fraction, 3),
                "stop_delay_ms": params.get("stop_delay_ms", 0),
            }
            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="preserved",
                similarity=1.0,
                reason="Semantic following behavior is directly representable on the target.",
                mapped_parameters=mapped,
                required_capabilities=tuple(sorted(required)),
            )

        if behavior_id == "navigation.pre_turn_observation":
            if not missing:
                return BehaviorMigrationResult(
                    behavior_id=behavior_id,
                    status="preserved",
                    similarity=1.0,
                    reason="Target provides directional attention before turning.",
                    mapped_parameters=params.copy(),
                    required_capabilities=tuple(sorted(required)),
                )

            if "navigation.planar_velocity" in available and "perception.forward_range" in available:
                mapped = {
                    "minimum_turn_deg": params.get("minimum_turn_deg", 70),
                    "observation_pause_ms": params.get("observation_pause_ms", 250),
                    "fallback": "base_yaw_preview",
                    "preview_yaw_deg": 8,
                }
                return BehaviorMigrationResult(
                    behavior_id=behavior_id,
                    status="approximated",
                    similarity=0.65,
                    reason=(
                        "Target lacks directional attention; adapter approximates the legacy "
                        "pre-turn observation with a small base-yaw preview."
                    ),
                    mapped_parameters=mapped,
                    required_capabilities=tuple(sorted(required)),
                    missing_capabilities=tuple(sorted(missing)),
                )

            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="unsupported",
                similarity=0.0,
                reason="No safe observable approximation is available on this target.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )

        return BehaviorMigrationResult(
            behavior_id=behavior_id,
            status="unsupported",
            similarity=0.0,
            reason="Example adapter does not implement this behavior namespace.",
            required_capabilities=tuple(sorted(required)),
            missing_capabilities=tuple(sorted(missing)),
        )
