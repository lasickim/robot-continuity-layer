from __future__ import annotations

import pytest

from rcl.profile import RCLValidationError
from rcl_ros2.target_execution_adapter import ROS2TargetExecutionAdapter


def _direct_instruction() -> dict:
    return {
        "constraint_id": "follow-distance",
        "behavior_id": "FOLLOW_USER",
        "dimension": "following_distance",
        "classification": "EXACT",
        "preservation_mode": "preference",
        "constraint_satisfied": True,
        "execution_status": "READY",
        "reason": "direct_target_mapping",
        "capability_id": "locomotion.following_geometry",
        "mapping_mode": "direct",
        "target_value": 0.82,
    }


def _substitute_instruction() -> dict:
    return {
        "constraint_id": "follow-gaze",
        "behavior_id": "FOLLOW_USER",
        "dimension": "gaze_before_move",
        "classification": "SUBSTITUTE",
        "preservation_mode": "identity_critical",
        "constraint_satisfied": True,
        "execution_status": "READY",
        "reason": "evidence_resolved_substitution",
        "capability_id": "expression.body_orientation_attention",
        "mapping_mode": "substitute",
        "substitution_strategy": "body_yaw_attention_cue",
        "assessed_fidelity": 0.8,
        "assessment_evidence_refs": ["physical://robot-b/gaze/run-01"],
    }


def test_direct_instruction_becomes_ros2_command_envelope():
    envelopes: list[dict] = []

    def sink(envelope: dict) -> dict:
        envelopes.append(envelope)
        return {"success": True, "evidence_refs": ["ros2://cmd/001"]}

    adapter = ROS2TargetExecutionAdapter(sink, target_robot_id="RCL-V05-SIM-B")
    result = adapter.execute(_direct_instruction())

    assert result["success"] is True
    assert result["evidence_refs"] == ["ros2://cmd/001"]
    assert envelopes[0]["command"] == "set_behavior_dimension"
    assert envelopes[0]["dimension"] == "following_distance"
    assert envelopes[0]["value"] == 0.82
    assert envelopes[0]["topic"] == "/rcl/target_execution"


def test_evidence_resolved_substitute_becomes_strategy_command():
    envelopes: list[dict] = []

    def sink(envelope: dict) -> None:
        envelopes.append(envelope)
        return None

    adapter = ROS2TargetExecutionAdapter(sink, target_robot_id="RCL-V05-SIM-B")
    result = adapter.execute(_substitute_instruction())

    assert result["success"] is True
    assert envelopes[0]["command"] == "execute_substitution_strategy"
    assert envelopes[0]["strategy"] == "body_yaw_attention_cue"
    assert envelopes[0]["assessed_fidelity"] == 0.8


def test_adapter_rejects_non_ready_instruction():
    instruction = _direct_instruction()
    instruction["execution_status"] = "REVIEW_REQUIRED"
    adapter = ROS2TargetExecutionAdapter(lambda _: None, target_robot_id="robot-b")
    with pytest.raises(RCLValidationError, match="READY instructions only"):
        adapter.execute(instruction)


def test_adapter_rejects_unresolved_substitute():
    instruction = _substitute_instruction()
    instruction.pop("assessed_fidelity")
    adapter = ROS2TargetExecutionAdapter(lambda _: None, target_robot_id="robot-b")
    with pytest.raises(RCLValidationError, match="assessed_fidelity"):
        adapter.execute(instruction)


def test_sink_failure_is_returned_to_target_execution_layer():
    adapter = ROS2TargetExecutionAdapter(
        lambda _: {"success": False, "evidence_refs": [], "message": "controller rejected"},
        target_robot_id="robot-b",
    )
    result = adapter.execute(_direct_instruction())
    assert result == {
        "success": False,
        "evidence_refs": [],
        "message": "controller rejected",
    }
