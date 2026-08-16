from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .adapter import RCLAdapter
from .hil_reference import build_hil_runtime_attestation, run_hil_reference_experiment
from .profile import RCLProfile, RCLValidationError, validate_schema


DISTANCE_SENSOR_HIL_VERSION = "0.1"
DISTANCE_SENSOR_HIL_METHOD = "rcl.hil.distance_sensor.v0.5"
DISTANCE_SENSOR_STRATEGY_ID = "target.direct_clearance_state"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_distance_reading_set(reading_set: dict[str, Any]) -> None:
    validate_schema(reading_set, "distance-sensor-reading-set")
    seen_sessions: set[str] = set()
    seen_trials: set[str] = set()
    for session in reading_set["sessions"]:
        session_id = session["session_id"]
        if session_id in seen_sessions:
            raise RCLValidationError(f"Duplicate distance-sensor session_id: {session_id}")
        seen_sessions.add(session_id)
        for trial in session["trials"]:
            trial_id = trial["trial_id"]
            if trial_id in seen_trials:
                raise RCLValidationError(f"Duplicate distance-sensor trial_id: {trial_id}")
            seen_trials.add(trial_id)


def distance_readings_to_intent_series(
    reading_set: dict[str, Any],
    *,
    robot_id: str,
    embodiment_id: str,
    behavior_id: str,
    trigger: str,
    success_condition: str,
    minimum_clearance_mm: float,
    strategy_id: str = DISTANCE_SENSOR_STRATEGY_ID,
) -> dict[str, Any]:
    """Convert measured distance readings into repeated Intent observations.

    A reading satisfies the clearance Intent when the measured distance is at or
    above the declared experiment threshold. The threshold is explicit input,
    not a universal RCL safety limit.
    """

    validate_distance_reading_set(reading_set)
    if minimum_clearance_mm <= 0:
        raise RCLValidationError("minimum_clearance_mm must be > 0")

    sessions: list[dict[str, Any]] = []
    for session in reading_set["sessions"]:
        trials: list[dict[str, Any]] = []
        for trial in session["trials"]:
            distance_mm = float(trial["distance_mm"])
            satisfied = distance_mm >= minimum_clearance_mm
            trials.append(
                {
                    "trial_id": trial["trial_id"],
                    "captured_at": trial["captured_at"],
                    "intent_observations": [
                        {
                            "observation_id": f"{trial['trial_id']}-intent",
                            "behavior_id": behavior_id,
                            "trigger": trigger,
                            "trigger_state": "observed",
                            "success_condition": success_condition,
                            "success_state": "satisfied" if satisfied else "not_satisfied",
                            "strategy_id": strategy_id,
                            "evidence_refs": list(trial.get("evidence_refs", [])),
                        }
                    ],
                }
            )
        sessions.append(
            {
                "session_id": session["session_id"],
                "started_at": session["started_at"],
                "trials": trials,
            }
        )

    series = {
        "intent_observation_series_version": "0.1",
        "series_id": f"{reading_set['reading_set_id']}-intent-series",
        "robot_id": robot_id,
        "embodiment_id": embodiment_id,
        "sessions": sessions,
    }
    validate_schema(series, "intent-observation-series")
    return series


def run_distance_sensor_hil_experiment(
    profile: RCLProfile,
    target_embodiment: dict[str, Any],
    source_series: dict[str, Any],
    reading_set: dict[str, Any],
    adapter: RCLAdapter,
    *,
    edge_component_id: str,
    sensor_component_id: str,
    behavior_id: str,
    trigger: str,
    success_condition: str,
    minimum_clearance_mm: float,
    evidence_refs: tuple[str, ...],
    deployment: bool,
    expected_target_path_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Run Phase-2 HIL using a measured distance-sensor reading set.

    Vendor-specific sensor drivers remain outside RCL core. The reading set is the
    portable evidence boundary: deployment code produces measured millimeters;
    RCL converts those readings into target Intent observations and feeds them to
    the same HIL evaluator used by other execution boundaries.
    """

    validate_distance_reading_set(reading_set)
    if reading_set["sensor_component_id"] != sensor_component_id:
        raise RCLValidationError(
            "sensor_component_id does not match the distance reading set"
        )

    timestamp = created_at or _now()
    target_series = distance_readings_to_intent_series(
        reading_set,
        robot_id=reading_set["robot_id"],
        embodiment_id=target_embodiment["embodiment_id"],
        behavior_id=behavior_id,
        trigger=trigger,
        success_condition=success_condition,
        minimum_clearance_mm=minimum_clearance_mm,
    )

    combined_refs = tuple(
        dict.fromkeys((*evidence_refs, *reading_set.get("evidence_refs", [])))
    )
    attestation = build_hil_runtime_attestation(
        component_id=edge_component_id,
        environment="deployment" if deployment else "unclassified",
        real_roles=("compute", "sensor"),
        simulated_roles=("plant", "actuator"),
        evidence_refs=combined_refs,
        captured_at=timestamp,
    )
    for component in attestation["real_components"]:
        if component["role"] == "sensor":
            component["component_id"] = sensor_component_id
    validate_schema(attestation, "hil-runtime-attestation")

    hil_report = run_hil_reference_experiment(
        profile,
        target_embodiment,
        source_series,
        target_series,
        adapter,
        attestation,
        behavior_id=behavior_id,
        expected_target_path_id=expected_target_path_id,
        created_at=timestamp,
    )

    report = {
        "distance_sensor_hil_version": DISTANCE_SENSOR_HIL_VERSION,
        "method": DISTANCE_SENSOR_HIL_METHOD,
        "created_at": timestamp,
        "reading_set_id": reading_set["reading_set_id"],
        "sensor_component_id": sensor_component_id,
        "minimum_clearance_mm": minimum_clearance_mm,
        "reading_count": sum(
            len(session["trials"]) for session in reading_set["sessions"]
        ),
        "strategy_id": DISTANCE_SENSOR_STRATEGY_ID,
        "hil_reference": hil_report,
        "assertions": {
            "reading_set_valid": True,
            "sensor_identity_matches": True,
            "hil_experiment_passed": bool(
                hil_report["assertions"]["experiment_passed"]
            ),
            "experiment_passed": bool(
                hil_report["assertions"]["experiment_passed"]
            ),
        },
        "disclaimer": (
            "Distance Sensor HIL v0.1 converts deployment-provided distance measurements into declared Intent observations. "
            "The clearance threshold is experiment-specific and is not a universal RCL safety limit. Sensor accuracy, calibration, placement, and physical safety remain deployment responsibilities."
        ),
    }
    validate_schema(report, "distance-sensor-hil-report")
    return report


def collect_distance_reading_set(
    reader: Callable[[], float],
    *,
    reading_set_id: str,
    robot_id: str,
    sensor_component_id: str,
    sessions: int = 3,
    trials_per_session: int = 3,
    evidence_ref_factory: Callable[[int, int], str] | None = None,
    clock: Callable[[], str] = _now,
) -> dict[str, Any]:
    """Collect a small repeated reading set from a deployment sensor reader.

    The caller supplies the actual driver as a zero-argument callable. CI may
    inject a fake reader; deployment code may inject VL53, lidar, serial, ROS 2,
    or another distance source without adding that dependency to RCL core.
    """

    if sessions < 1 or trials_per_session < 1:
        raise RCLValidationError("sessions and trials_per_session must be >= 1")

    output_sessions: list[dict[str, Any]] = []
    for session_index in range(1, sessions + 1):
        started_at = clock()
        trials: list[dict[str, Any]] = []
        for trial_index in range(1, trials_per_session + 1):
            distance_mm = float(reader())
            if distance_mm < 0:
                raise RCLValidationError("distance sensor returned a negative distance")
            refs: list[str] = []
            if evidence_ref_factory is not None:
                refs.append(evidence_ref_factory(session_index, trial_index))
            trials.append(
                {
                    "trial_id": f"{reading_set_id}-s{session_index:02d}-t{trial_index:02d}",
                    "captured_at": clock(),
                    "distance_mm": distance_mm,
                    "evidence_refs": refs,
                }
            )
        output_sessions.append(
            {
                "session_id": f"{reading_set_id}-session-{session_index:02d}",
                "started_at": started_at,
                "trials": trials,
            }
        )

    reading_set = {
        "distance_sensor_reading_set_version": "0.1",
        "reading_set_id": reading_set_id,
        "robot_id": robot_id,
        "sensor_component_id": sensor_component_id,
        "captured_at": clock(),
        "evidence_refs": [],
        "sessions": output_sessions,
    }
    validate_distance_reading_set(reading_set)
    return reading_set
