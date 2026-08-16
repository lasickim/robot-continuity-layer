import json
from pathlib import Path

from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.profile import RCLProfile
from rcl.sensor_evidence_hil import (
    distance_reading_set_to_sensor_evidence_series,
    run_sensor_evidence_hil_experiment,
    sensor_evidence_to_intent_series,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sensor_series(modality: str = "camera", state: str = "satisfied") -> dict:
    sessions = []
    for s in range(1, 4):
        trials = []
        for t in range(1, 4):
            trials.append({
                "trial_id": f"sensor-s{s:02d}-t{t:02d}",
                "captured_at": f"2026-08-16T10:{s:02d}:{t:02d}Z",
                "claims": [{
                    "claim_id": f"claim-s{s:02d}-t{t:02d}",
                    "semantic_state": "state.sitting_area_clear",
                    "state": state,
                    "confidence": 0.99,
                    "strategy_id": "target.direct_clearance_state",
                    "evidence_refs": [f"file://raw/s{s}-t{t}.json"],
                }],
            })
        sessions.append({
            "session_id": f"sensor-session-{s:02d}",
            "started_at": f"2026-08-16T10:{s:02d}:00Z",
            "trials": trials,
        })
    return {
        "sensor_evidence_series_version": "0.1",
        "series_id": "camera-demo",
        "robot_id": "RCL-V05-SIM-B",
        "sensor_component_id": "camera-01",
        "modality": modality,
        "evidence_refs": ["file://raw/session-manifest.json"],
        "sessions": sessions,
    }


def test_camera_semantic_claims_become_intent_observations():
    out = sensor_evidence_to_intent_series(
        _sensor_series(),
        embodiment_id="v05-sim-rover-b",
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        semantic_state="state.sitting_area_clear",
        default_strategy_id="target.direct_clearance_state",
    )
    obs = out["sessions"][0]["trials"][0]["intent_observations"][0]
    assert obs["success_state"] == "satisfied"
    assert obs["strategy_id"] == "target.direct_clearance_state"


def test_camera_hil_can_pass_with_same_intent_contract():
    root = _root()
    base = root / "examples" / "v0.5-sim"
    report = run_sensor_evidence_hil_experiment(
        RCLProfile.open(base / "robot-a"),
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _sensor_series(),
        CapabilityPathReferenceAdapter(),
        edge_component_id="edge-01",
        sensor_component_id="camera-01",
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        semantic_state="state.sitting_area_clear",
        default_strategy_id="target.direct_clearance_state",
        evidence_refs=("file://hil/runtime.json",),
        deployment=True,
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T10:05:00Z",
    )
    assert report["modality"] == "camera"
    assert report["hil_reference"]["evidence_grade"] == "HIL"
    assert report["experiment_passed"] is True


def test_tactile_uses_same_generic_contract():
    tactile = _sensor_series(modality="tactile")
    tactile["sensor_component_id"] = "tactile-01"
    assert tactile["modality"] == "tactile"
    out = sensor_evidence_to_intent_series(
        tactile,
        embodiment_id="v05-sim-rover-b",
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        semantic_state="state.sitting_area_clear",
        default_strategy_id="target.direct_clearance_state",
    )
    assert len(out["sessions"]) == 3


def test_distance_bridge_adapts_into_generic_sensor_evidence():
    reading_set = {
        "distance_sensor_reading_set_version": "0.1",
        "reading_set_id": "distance-demo",
        "robot_id": "RCL-V05-SIM-B",
        "sensor_component_id": "tof-01",
        "captured_at": "2026-08-16T11:00:00Z",
        "evidence_refs": [],
        "sessions": [{
            "session_id": "s1",
            "started_at": "2026-08-16T11:00:00Z",
            "trials": [{
                "trial_id": "t1",
                "captured_at": "2026-08-16T11:00:01Z",
                "distance_mm": 450.0,
                "evidence_refs": ["file://raw/tof.json"],
            }],
        }],
    }
    generic = distance_reading_set_to_sensor_evidence_series(
        reading_set, minimum_clearance_mm=300.0
    )
    assert generic["modality"] == "distance"
    assert generic["sessions"][0]["trials"][0]["claims"][0]["state"] == "satisfied"


def test_sensor_evidence_schema_runtime_public_parity():
    root = _root()
    runtime = _read(root / "rcl" / "schemas" / "sensor-evidence-series.schema.json")
    public = _read(root / "spec" / "schemas" / "sensor-evidence-series.schema.json")
    assert runtime == public
