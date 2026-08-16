import json
from pathlib import Path

import pytest

from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.distance_sensor_hil import (
    collect_distance_reading_set,
    distance_readings_to_intent_series,
    run_distance_sensor_hil_experiment,
)
from rcl.profile import RCLProfile, RCLValidationError, validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _reading_set(distance_mm: float = 500.0) -> dict:
    sessions = []
    for session_index in range(1, 4):
        trials = []
        for trial_index in range(1, 4):
            trials.append(
                {
                    "trial_id": f"sensor-s{session_index:02d}-t{trial_index:02d}",
                    "captured_at": f"2026-08-16T08:{session_index:02d}:{trial_index:02d}Z",
                    "distance_mm": distance_mm,
                    "evidence_refs": [
                        f"file://sensor-log/s{session_index:02d}-t{trial_index:02d}.json"
                    ],
                }
            )
        sessions.append(
            {
                "session_id": f"sensor-session-{session_index:02d}",
                "started_at": f"2026-08-16T08:{session_index:02d}:00Z",
                "trials": trials,
            }
        )
    return {
        "distance_sensor_reading_set_version": "0.1",
        "reading_set_id": "distance-hil-demo",
        "robot_id": "RCL-V05-SIM-B",
        "sensor_component_id": "tof-01",
        "captured_at": "2026-08-16T08:04:00Z",
        "evidence_refs": ["file://sensor-log/session-manifest.json"],
        "sessions": sessions,
    }


def _run(*, deployment: bool, distance_mm: float = 500.0) -> dict:
    root = _root()
    base = root / "examples" / "v0.5-sim"
    return run_distance_sensor_hil_experiment(
        RCLProfile.open(base / "robot-a"),
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _reading_set(distance_mm),
        CapabilityPathReferenceAdapter(),
        edge_component_id="edge-01",
        sensor_component_id="tof-01",
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        minimum_clearance_mm=300.0,
        evidence_refs=("file://hil/runtime.json",),
        deployment=deployment,
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T08:05:00Z",
    )


def test_distance_readings_become_target_intent_evidence():
    series = distance_readings_to_intent_series(
        _reading_set(),
        robot_id="RCL-V05-SIM-B",
        embodiment_id="v05-sim-rover-b",
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        minimum_clearance_mm=300.0,
    )
    assert len(series["sessions"]) == 3
    assert series["sessions"][0]["trials"][0]["intent_observations"][0]["success_state"] == "satisfied"


def test_unclassified_compute_does_not_become_hil_evidence():
    report = _run(deployment=False)
    validate_schema(report, "distance-sensor-hil-report")
    assert report["hil_reference"]["evidence_grade"] == "UNCLASSIFIED"
    assert report["assertions"]["experiment_passed"] is False


def test_declared_deployment_with_sensor_measurements_can_pass_hil():
    report = _run(deployment=True)
    validate_schema(report, "distance-sensor-hil-report")
    assert report["hil_reference"]["evidence_grade"] == "HIL"
    assert report["hil_reference"]["attestation"]["real_components"] == [
        {"role": "compute", "component_id": "edge-01"},
        {"role": "sensor", "component_id": "tof-01"},
    ]
    assert report["reading_count"] == 9
    assert report["assertions"]["experiment_passed"] is True


def test_failed_clearance_measurements_fail_semantic_hil():
    report = _run(deployment=True, distance_mm=100.0)
    assert report["hil_reference"]["evidence_grade"] == "HIL"
    assert report["hil_reference"]["status"] == "semantic_failure"
    assert report["assertions"]["experiment_passed"] is False


def test_reading_set_sensor_identity_must_match_declared_sensor():
    root = _root()
    base = root / "examples" / "v0.5-sim"
    with pytest.raises(RCLValidationError, match="sensor_component_id"):
        run_distance_sensor_hil_experiment(
            RCLProfile.open(base / "robot-a"),
            _read(base / "robot-b.embodiment.json"),
            _read(base / "robot-a.intent-series.json"),
            _reading_set(),
            CapabilityPathReferenceAdapter(),
            edge_component_id="edge-01",
            sensor_component_id="different-sensor",
            behavior_id="safety.pre_sit_clearance_check",
            trigger="activity.before_sit_down",
            success_condition="state.sitting_area_clear",
            minimum_clearance_mm=300.0,
            evidence_refs=("file://hil/runtime.json",),
            deployment=True,
        )


def test_collect_distance_reading_set_accepts_injected_driver():
    values = iter([401.0, 402.0, 403.0, 404.0])
    ticks = iter(
        [
            "2026-08-16T09:00:00Z",
            "2026-08-16T09:00:01Z",
            "2026-08-16T09:00:02Z",
            "2026-08-16T09:01:00Z",
            "2026-08-16T09:01:01Z",
            "2026-08-16T09:01:02Z",
            "2026-08-16T09:02:00Z",
        ]
    )
    reading_set = collect_distance_reading_set(
        lambda: next(values),
        reading_set_id="driver-demo",
        robot_id="robot-b",
        sensor_component_id="tof-01",
        sessions=2,
        trials_per_session=2,
        evidence_ref_factory=lambda s, t: f"file://raw/s{s}-t{t}.json",
        clock=lambda: next(ticks),
    )
    assert reading_set["sessions"][1]["trials"][1]["distance_mm"] == 404.0
    assert reading_set["sessions"][0]["trials"][0]["evidence_refs"] == [
        "file://raw/s1-t1.json"
    ]


def test_distance_sensor_schema_is_published_with_runtime_parity():
    root = _root()
    for name in (
        "distance-sensor-reading-set.schema.json",
        "distance-sensor-hil-report.schema.json",
    ):
        runtime = _read(root / "rcl" / "schemas" / name)
        published = _read(root / "spec" / "schemas" / name)
        assert runtime == published
