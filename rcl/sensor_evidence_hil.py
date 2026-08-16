from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .adapter import RCLAdapter
from .hil_reference import build_hil_runtime_attestation, run_hil_reference_experiment
from .profile import RCLProfile, RCLValidationError, validate_schema


SENSOR_EVIDENCE_HIL_VERSION = "0.1"
SENSOR_EVIDENCE_HIL_METHOD = "rcl.hil.sensor_evidence.v0.5"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_sensor_evidence_series(series: dict[str, Any]) -> None:
    validate_schema(series, "sensor-evidence-series")
    seen_sessions: set[str] = set()
    seen_trials: set[str] = set()
    seen_claims: set[str] = set()
    for session in series["sessions"]:
        if session["session_id"] in seen_sessions:
            raise RCLValidationError(f"Duplicate sensor evidence session_id: {session['session_id']}")
        seen_sessions.add(session["session_id"])
        for trial in session["trials"]:
            if trial["trial_id"] in seen_trials:
                raise RCLValidationError(f"Duplicate sensor evidence trial_id: {trial['trial_id']}")
            seen_trials.add(trial["trial_id"])
            for claim in trial["claims"]:
                if claim["claim_id"] in seen_claims:
                    raise RCLValidationError(f"Duplicate sensor evidence claim_id: {claim['claim_id']}")
                seen_claims.add(claim["claim_id"])


def sensor_evidence_to_intent_series(
    series: dict[str, Any],
    *,
    embodiment_id: str,
    behavior_id: str,
    trigger: str,
    success_condition: str,
    semantic_state: str,
    default_strategy_id: str,
) -> dict[str, Any]:
    """Map one declared semantic sensor state into repeated Intent observations."""

    validate_sensor_evidence_series(series)
    sessions: list[dict[str, Any]] = []
    for session in series["sessions"]:
        trials: list[dict[str, Any]] = []
        for trial in session["trials"]:
            matches = [c for c in trial["claims"] if c["semantic_state"] == semantic_state]
            if len(matches) != 1:
                raise RCLValidationError(
                    f"Trial {trial['trial_id']!r} must contain exactly one claim for {semantic_state!r}"
                )
            claim = matches[0]
            trials.append(
                {
                    "trial_id": trial["trial_id"],
                    "captured_at": trial["captured_at"],
                    "intent_observations": [
                        {
                            "observation_id": f"{claim['claim_id']}-intent",
                            "behavior_id": behavior_id,
                            "trigger": trigger,
                            "trigger_state": "observed",
                            "success_condition": success_condition,
                            "success_state": claim["state"],
                            "strategy_id": claim.get("strategy_id", default_strategy_id),
                            "evidence_refs": list(claim.get("evidence_refs", [])),
                        }
                    ],
                }
            )
        sessions.append(
            {"session_id": session["session_id"], "started_at": session["started_at"], "trials": trials}
        )

    output = {
        "intent_observation_series_version": "0.1",
        "series_id": f"{series['series_id']}-intent-series",
        "robot_id": series["robot_id"],
        "embodiment_id": embodiment_id,
        "sessions": sessions,
    }
    validate_schema(output, "intent-observation-series")
    return output


def run_sensor_evidence_hil_experiment(
    profile: RCLProfile,
    target_embodiment: dict[str, Any],
    source_series: dict[str, Any],
    sensor_series: dict[str, Any],
    adapter: RCLAdapter,
    *,
    edge_component_id: str,
    sensor_component_id: str,
    behavior_id: str,
    trigger: str,
    success_condition: str,
    semantic_state: str,
    default_strategy_id: str,
    evidence_refs: tuple[str, ...],
    deployment: bool,
    expected_target_path_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Run HIL with vendor-neutral semantic sensor claims."""

    validate_sensor_evidence_series(sensor_series)
    if sensor_series["sensor_component_id"] != sensor_component_id:
        raise RCLValidationError("sensor_component_id does not match sensor evidence series")

    timestamp = created_at or _now()
    target_series = sensor_evidence_to_intent_series(
        sensor_series,
        embodiment_id=target_embodiment["embodiment_id"],
        behavior_id=behavior_id,
        trigger=trigger,
        success_condition=success_condition,
        semantic_state=semantic_state,
        default_strategy_id=default_strategy_id,
    )
    combined_refs = tuple(dict.fromkeys((*evidence_refs, *sensor_series.get("evidence_refs", []))))
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
    return {
        "sensor_evidence_hil_version": SENSOR_EVIDENCE_HIL_VERSION,
        "method": SENSOR_EVIDENCE_HIL_METHOD,
        "created_at": timestamp,
        "sensor_component_id": sensor_component_id,
        "modality": sensor_series["modality"],
        "semantic_state": semantic_state,
        "hil_reference": hil_report,
        "experiment_passed": bool(hil_report["assertions"]["experiment_passed"]),
    }


def distance_reading_set_to_sensor_evidence_series(
    reading_set: dict[str, Any],
    *,
    minimum_clearance_mm: float,
    semantic_state: str = "state.sitting_area_clear",
    strategy_id: str = "target.direct_clearance_state",
) -> dict[str, Any]:
    """Adapt the existing distance-reading boundary into generic sensor evidence."""

    from .distance_sensor_hil import validate_distance_reading_set

    validate_distance_reading_set(reading_set)
    if minimum_clearance_mm <= 0:
        raise RCLValidationError("minimum_clearance_mm must be > 0")
    sessions: list[dict[str, Any]] = []
    for session in reading_set["sessions"]:
        trials: list[dict[str, Any]] = []
        for trial in session["trials"]:
            trials.append(
                {
                    "trial_id": trial["trial_id"],
                    "captured_at": trial["captured_at"],
                    "claims": [
                        {
                            "claim_id": f"{trial['trial_id']}-clearance",
                            "semantic_state": semantic_state,
                            "state": "satisfied" if float(trial["distance_mm"]) >= minimum_clearance_mm else "not_satisfied",
                            "strategy_id": strategy_id,
                            "evidence_refs": list(trial.get("evidence_refs", [])),
                        }
                    ],
                }
            )
        sessions.append({"session_id": session["session_id"], "started_at": session["started_at"], "trials": trials})
    output = {
        "sensor_evidence_series_version": "0.1",
        "series_id": f"{reading_set['reading_set_id']}-sensor-evidence",
        "robot_id": reading_set["robot_id"],
        "sensor_component_id": reading_set["sensor_component_id"],
        "modality": "distance",
        "evidence_refs": list(reading_set.get("evidence_refs", [])),
        "sessions": sessions,
    }
    validate_sensor_evidence_series(output)
    return output
