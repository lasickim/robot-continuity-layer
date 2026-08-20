from __future__ import annotations

from typing import Any, Callable

from rcl.profile import RCLValidationError


CommandSink = Callable[[dict[str, Any]], dict[str, Any] | None]


class ROS2TargetExecutionAdapter:
    """Reference TargetExecutionAdapter for ROS 2 / Jetson deployments.

    The adapter converts RCL READY instructions into a vendor-neutral ROS-facing
    command envelope. A deployment-provided ``command_sink`` owns the actual
    ROS publication, service call, action request, or Jetson controller bridge.

    Importing this module never requires ROS 2.
    """

    adapter_id = "rcl.ros2.target_execution"
    adapter_version = "0.1"

    def __init__(
        self,
        command_sink: CommandSink,
        *,
        target_robot_id: str,
        command_topic: str = "/rcl/target_execution",
    ) -> None:
        if not callable(command_sink):
            raise ValueError("command_sink must be callable")
        if not target_robot_id:
            raise ValueError("target_robot_id must not be empty")
        if not command_topic:
            raise ValueError("command_topic must not be empty")
        self._command_sink = command_sink
        self.target_robot_id = target_robot_id
        self.command_topic = command_topic

    def _command_for_instruction(self, instruction: dict[str, Any]) -> dict[str, Any]:
        if instruction.get("execution_status") != "READY":
            raise RCLValidationError("ROS2 target adapter accepts READY instructions only")
        if not instruction.get("constraint_satisfied"):
            raise RCLValidationError("ROS2 target adapter rejects policy-unsatisfied instruction")

        mode = instruction.get("mapping_mode")
        dimension = instruction.get("dimension")
        capability_id = instruction.get("capability_id")
        if not dimension or not capability_id:
            raise RCLValidationError("execution instruction lacks dimension or capability_id")

        envelope: dict[str, Any] = {
            "command_envelope_version": "0.1",
            "target_robot_id": self.target_robot_id,
            "transport": "ros2",
            "topic": self.command_topic,
            "constraint_id": instruction["constraint_id"],
            "behavior_id": instruction["behavior_id"],
            "dimension": dimension,
            "capability_id": capability_id,
            "mapping_mode": mode,
        }

        if mode == "direct":
            if "target_value" not in instruction:
                raise RCLValidationError("direct instruction lacks target_value")
            envelope.update(
                {
                    "command": "set_behavior_dimension",
                    "value": instruction["target_value"],
                }
            )
            if "absolute_error" in instruction:
                envelope["compile_absolute_error"] = instruction["absolute_error"]
            return envelope

        if mode == "substitute":
            strategy = instruction.get("substitution_strategy")
            fidelity = instruction.get("assessed_fidelity")
            if not strategy:
                raise RCLValidationError("substitute instruction lacks substitution_strategy")
            if fidelity is None:
                raise RCLValidationError("substitute instruction lacks assessed_fidelity")
            envelope.update(
                {
                    "command": "execute_substitution_strategy",
                    "strategy": strategy,
                    "assessed_fidelity": fidelity,
                }
            )
            if "assessment_evidence_refs" in instruction:
                envelope["assessment_evidence_refs"] = list(
                    instruction["assessment_evidence_refs"]
                )
            return envelope

        raise RCLValidationError(f"unsupported mapping_mode for ROS2 execution: {mode}")

    def execute(self, instruction: dict[str, Any]) -> dict[str, Any]:
        envelope = self._command_for_instruction(instruction)
        raw = self._command_sink(envelope)
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise RCLValidationError("command_sink must return an object or None")

        success = raw.get("success", True)
        if not isinstance(success, bool):
            raise RCLValidationError("command_sink success must be boolean")

        evidence_refs = raw.get("evidence_refs", [])
        if not isinstance(evidence_refs, list) or any(
            not isinstance(ref, str) or not ref for ref in evidence_refs
        ):
            raise RCLValidationError("command_sink evidence_refs must be non-empty strings")

        result: dict[str, Any] = {
            "success": success,
            "evidence_refs": evidence_refs,
            "message": raw.get(
                "message",
                f"ROS2 command envelope accepted: {envelope['command']}",
            ),
        }
        if not isinstance(result["message"], str) or not result["message"]:
            raise RCLValidationError("command_sink message must be a non-empty string")
        return result


class ROS2JsonPublisherSink:
    """Optional ROS 2 runtime sink using ``std_msgs/msg/String`` JSON payloads.

    ROS imports are lazy so unit tests and non-ROS hosts can import the module.
    This reference transport is intentionally generic; production deployments
    may replace it with typed messages, services, actions, or controller APIs.
    """

    def __init__(self, node: Any, *, topic: str = "/rcl/target_execution", qos_depth: int = 10) -> None:
        if not topic:
            raise ValueError("topic must not be empty")
        if qos_depth <= 0:
            raise ValueError("qos_depth must be positive")
        try:
            from std_msgs.msg import String
        except ImportError as exc:  # pragma: no cover - depends on ROS installation
            raise RuntimeError(
                "ROS 2 std_msgs is not available. Source a ROS 2 environment before constructing ROS2JsonPublisherSink."
            ) from exc
        self._string_type = String
        self._publisher = node.create_publisher(String, topic, qos_depth)

    def __call__(self, envelope: dict[str, Any]) -> dict[str, Any]:
        import json

        message = self._string_type()
        message.data = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        self._publisher.publish(message)
        return {
            "success": True,
            "evidence_refs": [],
            "message": "ROS2 command envelope published",
        }
