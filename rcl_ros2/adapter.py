from __future__ import annotations

from typing import Any

from rcl.adapter import BehaviorMigrationResult, RCLAdapter


class ROS2MobileBaseAdapter(RCLAdapter):
    """Reference semantic adapter for a ROS 2 planar mobile base.

    The adapter translates portable RCL behavior into a ROS-facing execution
    plan. It does not publish to ROS directly; runtime publication belongs to
    the integration layer in ``rcl_ros2.runtime``.
    """

    adapter_id = "rcl.ros2.mobile_base"
    adapter_version = "0.3-dev"

    def __init__(
        self,
        *,
        cmd_vel_topic: str = "/cmd_vel",
        control_rate_hz: float = 10.0,
        message_type: str = "geometry_msgs/msg/Twist",
    ) -> None:
        if not cmd_vel_topic:
            raise ValueError("cmd_vel_topic must not be empty")
        if control_rate_hz <= 0:
            raise ValueError("control_rate_hz must be positive")
        self.cmd_vel_topic = cmd_vel_topic
        self.control_rate_hz = float(control_rate_hz)
        self.message_type = message_type

    def supports(self, target_embodiment: dict[str, Any]) -> bool:
        return (
            target_embodiment.get("class") == "mobile_base"
            and "navigation.planar_velocity"
            in set(target_embodiment.get("capabilities", []))
        )

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

    def _ros2_velocity_interface(self) -> dict[str, Any]:
        return {
            "transport": "topic",
            "topic": self.cmd_vel_topic,
            "message_type": self.message_type,
            "control_rate_hz": self.control_rate_hz,
        }

    def translate_behavior(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> BehaviorMigrationResult:
        del source_embodiment  # reserved for future source/target comparative logic

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
                    reason=(
                        "ROS 2 target lacks one or more capabilities required "
                        "for semantic person following."
                    ),
                    required_capabilities=tuple(sorted(required)),
                    missing_capabilities=tuple(sorted(missing)),
                )

            speed_fraction = {
                "gentle": 0.35,
                "normal": 0.55,
                "brisk": 0.75,
            }.get(params.get("speed_style"), 0.55)
            turn_fraction = 0.45 if params.get("turn_style") == "cautious" else 0.70

            max_linear = float(limits.get("max_linear_speed_mps", 1.0))
            max_angular = float(limits.get("max_angular_speed_rps", 1.0))

            mapped = {
                "following_distance_m": float(
                    params.get("preferred_distance_m", 1.0)
                ),
                "linear_speed_limit_mps": round(max_linear * speed_fraction, 3),
                "angular_speed_limit_rps": round(max_angular * turn_fraction, 3),
                "stop_delay_ms": int(params.get("stop_delay_ms", 0)),
                "execution": {
                    "controller": "planar_velocity",
                    "ros2_interface": self._ros2_velocity_interface(),
                },
            }
            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="preserved",
                similarity=1.0,
                reason=(
                    "The target exposes planar velocity and person tracking; "
                    "the semantic following style can be represented through "
                    "a ROS 2 velocity execution plan."
                ),
                mapped_parameters=mapped,
                required_capabilities=tuple(sorted(required)),
            )

        if behavior_id == "navigation.pre_turn_observation":
            if not missing:
                mapped = dict(params)
                mapped["execution"] = {
                    "controller": "directional_attention_hook",
                    "ros2_interface": self._ros2_velocity_interface(),
                }
                return BehaviorMigrationResult(
                    behavior_id=behavior_id,
                    status="preserved",
                    similarity=1.0,
                    reason=(
                        "The target exposes directional attention before a turn."
                    ),
                    mapped_parameters=mapped,
                    required_capabilities=tuple(sorted(required)),
                )

            can_preview = {
                "navigation.planar_velocity",
                "perception.forward_range",
            }.issubset(available)
            if can_preview:
                mapped = {
                    "minimum_turn_deg": params.get("minimum_turn_deg", 70),
                    "observation_pause_ms": params.get(
                        "observation_pause_ms", 250
                    ),
                    "preview_yaw_deg": 8,
                    "execution": {
                        "controller": "base_yaw_preview",
                        "ros2_interface": self._ros2_velocity_interface(),
                    },
                }
                return BehaviorMigrationResult(
                    behavior_id=behavior_id,
                    status="approximated",
                    similarity=0.65,
                    reason=(
                        "The target lacks directional attention; the adapter "
                        "approximates the legacy pre-turn observation with a "
                        "small velocity-controlled base yaw preview."
                    ),
                    mapped_parameters=mapped,
                    required_capabilities=tuple(sorted(required)),
                    missing_capabilities=tuple(sorted(missing)),
                )

            return BehaviorMigrationResult(
                behavior_id=behavior_id,
                status="unsupported",
                similarity=0.0,
                reason=(
                    "The ROS 2 target has no safe observable approximation for "
                    "pre-turn observation."
                ),
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )

        return BehaviorMigrationResult(
            behavior_id=behavior_id,
            status="unsupported",
            similarity=0.0,
            reason="ROS 2 reference adapter does not implement this behavior namespace.",
            required_capabilities=tuple(sorted(required)),
            missing_capabilities=tuple(sorted(missing)),
        )
