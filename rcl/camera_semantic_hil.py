from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .adapter import RCLAdapter
from .profile import RCLProfile, RCLValidationError, validate_schema
from .sensor_evidence_hil import (
    run_sensor_evidence_hil_experiment,
    validate_sensor_evidence_series,
)


CAMERA_SEMANTIC_HIL_VERSION = "0.1"
CAMERA_SEMANTIC_HIL_METHOD = "rcl.hil.camera_semantic.v0.5"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_camera_perception_series(series: dict[str, Any]) -> None:
    validate_schema(series, "camera-perception-series")
    seen_sessions: set[str] = set()
    seen_trials: set[str] = set()
    seen_inferences: set[str] = set()
    for session in series["sessions"]:
        session_id = session["session_id"]
        if session_id in seen_sessions:
            raise RCLValidationError(f"Duplicate camera session_id: {session_id}")
        seen_sessions.add(session_id)
        for trial in session["trials"]:
            trial_id = trial["trial_id"]
            if trial_id in seen_trials:
                raise RCLValidationError(f"Duplicate camera trial_id: {trial_id}")
            seen_trials.add(trial_id)
            for inference in trial["inferences"]:
                inference_id = inference["inference_id"]
                if inference_id in seen_inferences:
                    raise RCLValidationError(
                        f"Duplicate camera inference_id: {inference_id}"
                    )
                seen_inferences.add(inference_id)


def camera_perception_to_sensor_evidence_series(
    perception_series: dict[str, Any],
    *,
    minimum_confidence: float,
    default_strategy_id: str,
) -> dict[str, Any]:
    """Convert camera inference results into generic semantic sensor evidence.

    Confidence below the declared experiment threshold becomes not_observable
    rather than a guessed satisfied/not_satisfied state. The threshold is an
    experiment policy and is not a universal RCL perception requirement.
    """

    validate_camera_perception_series(perception_series)
    if not 0 <= minimum_confidence <= 1:
        raise RCLValidationError("minimum_confidence must be between 0 and 1")

    sessions: list[dict[str, Any]] = []
    for session in perception_series["sessions"]:
        trials: list[dict[str, Any]] = []
        for trial in session["trials"]:
            claims: list[dict[str, Any]] = []
            frame_ref = trial["frame_ref"]
            for inference in trial["inferences"]:
                confidence = float(inference["confidence"])
                if confidence < minimum_confidence:
                    state = "not_observable"
                else:
                    state = (
                        "satisfied"
                        if bool(inference["predicate"])
                        else "not_satisfied"
                    )
                evidence_refs = list(
                    dict.fromkeys(
                        [frame_ref, *inference.get("evidence_refs", [])]
                    )
                )
                claims.append(
                    {
                        "claim_id": inference["inference_id"],
                        "semantic_state": inference["semantic_state"],
                        "state": state,
                        "confidence": confidence,
                        "strategy_id": inference.get(
                            "strategy_id", default_strategy_id
                        ),
                        "evidence_refs": evidence_refs,
                    }
                )
            trials.append(
                {
                    "trial_id": trial["trial_id"],
                    "captured_at": trial["captured_at"],
                    "claims": claims,
                }
            )
        sessions.append(
            {
                "session_id": session["session_id"],
                "started_at": session["started_at"],
                "trials": trials,
            }
        )

    output = {
        "sensor_evidence_series_version": "0.1",
        "series_id": f"{perception_series['series_id']}-sensor-evidence",
        "robot_id": perception_series["robot_id"],
        "sensor_component_id": perception_series["sensor_component_id"],
        "modality": "camera",
        "evidence_refs": list(perception_series.get("evidence_refs", [])),
        "sessions": sessions,
    }
    validate_sensor_evidence_series(output)
    return output


def run_camera_semantic_hil_experiment(
    profile: RCLProfile,
    target_embodiment: dict[str, Any],
    source_series: dict[str, Any],
    perception_series: dict[str, Any],
    adapter: RCLAdapter,
    *,
    edge_component_id: str,
    camera_component_id: str,
    behavior_id: str,
    trigger: str,
    success_condition: str,
    semantic_state: str,
    default_strategy_id: str,
    minimum_confidence: float,
    evidence_refs: tuple[str, ...],
    deployment: bool,
    expected_target_path_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Run Phase-2 HIL using camera-derived semantic evidence."""

    validate_camera_perception_series(perception_series)
    if perception_series["sensor_component_id"] != camera_component_id:
        raise RCLValidationError(
            "camera_component_id does not match camera perception series"
        )

    timestamp = created_at or _now()
    sensor_series = camera_perception_to_sensor_evidence_series(
        perception_series,
        minimum_confidence=minimum_confidence,
        default_strategy_id=default_strategy_id,
    )
    combined_refs = tuple(
        dict.fromkeys(
            (*evidence_refs, *perception_series.get("evidence_refs", []))
        )
    )
    generic_report = run_sensor_evidence_hil_experiment(
        profile,
        target_embodiment,
        source_series,
        sensor_series,
        adapter,
        edge_component_id=edge_component_id,
        sensor_component_id=camera_component_id,
        behavior_id=behavior_id,
        trigger=trigger,
        success_condition=success_condition,
        semantic_state=semantic_state,
        default_strategy_id=default_strategy_id,
        evidence_refs=combined_refs,
        deployment=deployment,
        expected_target_path_id=expected_target_path_id,
        created_at=timestamp,
    )

    inference_count = sum(
        len(trial["inferences"])
        for session in perception_series["sessions"]
        for trial in session["trials"]
    )
    low_confidence_count = sum(
        1
        for session in perception_series["sessions"]
        for trial in session["trials"]
        for inference in trial["inferences"]
        if float(inference["confidence"]) < minimum_confidence
    )

    return {
        "camera_semantic_hil_version": CAMERA_SEMANTIC_HIL_VERSION,
        "method": CAMERA_SEMANTIC_HIL_METHOD,
        "created_at": timestamp,
        "camera_component_id": camera_component_id,
        "model": perception_series["model"],
        "minimum_confidence": minimum_confidence,
        "inference_count": inference_count,
        "low_confidence_count": low_confidence_count,
        "sensor_evidence_hil": generic_report,
        "experiment_passed": bool(generic_report["experiment_passed"]),
        "disclaimer": (
            "Camera Semantic HIL v0.1 records deployment-provided camera inference results and confidence. "
            "It does not certify model accuracy, camera calibration, scene coverage, occlusion robustness, or physical safety."
        ),
    }
