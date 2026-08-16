import json
from pathlib import Path

import pytest

from rcl.camera_semantic_hil import (
    camera_perception_to_sensor_evidence_series,
    run_camera_semantic_hil_experiment,
)
from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.profile import RCLProfile, RCLValidationError


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _perception(*, confidence: float = 0.95, predicate: bool = True) -> dict:
    sessions = []
    for s in range(1, 4):
        trials = []
        for t in range(1, 4):
            trials.append(
                {
                    "trial_id": f"cam-s{s:02d}-t{t:02d}",
                    "captured_at": f"2026-08-16T10:{s:02d}:{t:02d}Z",
                    "frame_ref": f"file://camera/frames/s{s:02d}-t{t:02d}.jpg",
                    "inferences": [
                        {
                            "inference_id": f"cam-inf-s{s:02d}-t{t:02d}",
                            "semantic_state": "state.sitting_area_clear",
                            "predicate": predicate,
                            "confidence": confidence,
                            "strategy_id": "target.direct_clearance_state",
                            "evidence_refs": [f"file://camera/inference/s{s:02d}-t{t:02d}.json"],
                        }
                    ],
                }
            )
        sessions.append(
            {
                "session_id": f"cam-session-{s:02d}",
                "started_at": f"2026-08-16T10:{s:02d}:00Z",
                "trials": trials,
            }
        )
    return {
        "camera_perception_series_version": "0.1",
        "series_id": "camera-hil-demo",
        "robot_id": "RCL-V05-SIM-B",
        "sensor_component_id": "camera-01",
        "model": {"model_id": "demo-clearance-model", "runtime": "test", "version": "0.1"},
        "evidence_refs": ["file://camera/session-manifest.json"],
        "sessions": sessions,
    }


def _run(*, deployment: bool, confidence: float = 0.95, predicate: bool = True) -> dict:
    root = _root()
    base = root / "examples" / "v0.5-sim"
    return run_camera_semantic_hil_experiment(
        RCLProfile.open(base / "robot-a"),
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _perception(confidence=confidence, predicate=predicate),
        CapabilityPathReferenceAdapter(),
        edge_component_id="edge-01",
        camera_component_id="camera-01",
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        semantic_state="state.sitting_area_clear",
        default_strategy_id="target.direct_clearance_state",
        minimum_confidence=0.80,
        evidence_refs=("file://hil/runtime.json",),
        deployment=deployment,
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T10:05:00Z",
    )


def test_camera_inference_becomes_generic_sensor_evidence():
    series = camera_perception_to_sensor_evidence_series(
        _perception(),
        minimum_confidence=0.80,
        default_strategy_id="target.direct_clearance_state",
    )
    claim = series["sessions"][0]["trials"][0]["claims"][0]
    assert series["modality"] == "camera"
    assert claim["state"] == "satisfied"
    assert claim["confidence"] == 0.95
    assert claim["evidence_refs"][0].endswith(".jpg")


def test_low_confidence_camera_inference_is_not_observable():
    series = camera_perception_to_sensor_evidence_series(
        _perception(confidence=0.50),
        minimum_confidence=0.80,
        default_strategy_id="target.direct_clearance_state",
    )
    claim = series["sessions"][0]["trials"][0]["claims"][0]
    assert claim["state"] == "not_observable"


def test_camera_hil_can_pass_only_on_declared_deployment():
    unclassified = _run(deployment=False)
    deployed = _run(deployment=True)
    assert unclassified["experiment_passed"] is False
    assert unclassified["sensor_evidence_hil"]["hil_reference"]["evidence_grade"] == "UNCLASSIFIED"
    assert deployed["experiment_passed"] is True
    assert deployed["sensor_evidence_hil"]["hil_reference"]["evidence_grade"] == "HIL"


def test_negative_camera_predicate_fails_semantically():
    report = _run(deployment=True, predicate=False)
    assert report["sensor_evidence_hil"]["hil_reference"]["evidence_grade"] == "HIL"
    assert report["experiment_passed"] is False


def test_low_confidence_camera_run_does_not_pass_semantically():
    report = _run(deployment=True, confidence=0.50)
    assert report["low_confidence_count"] == 9
    assert report["experiment_passed"] is False


def test_camera_identity_must_match_declared_component():
    root = _root()
    base = root / "examples" / "v0.5-sim"
    with pytest.raises(RCLValidationError, match="camera_component_id"):
        run_camera_semantic_hil_experiment(
            RCLProfile.open(base / "robot-a"),
            _read(base / "robot-b.embodiment.json"),
            _read(base / "robot-a.intent-series.json"),
            _perception(),
            CapabilityPathReferenceAdapter(),
            edge_component_id="edge-01",
            camera_component_id="different-camera",
            behavior_id="safety.pre_sit_clearance_check",
            trigger="activity.before_sit_down",
            success_condition="state.sitting_area_clear",
            semantic_state="state.sitting_area_clear",
            default_strategy_id="target.direct_clearance_state",
            minimum_confidence=0.80,
            evidence_refs=("file://hil/runtime.json",),
            deployment=True,
        )


def test_camera_schema_runtime_public_parity():
    root = _root()
    assert _read(root / "rcl" / "schemas" / "camera-perception-series.schema.json") == _read(
        root / "spec" / "schemas" / "camera-perception-series.schema.json"
    )
