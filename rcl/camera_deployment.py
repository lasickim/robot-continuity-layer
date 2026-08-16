from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .camera_semantic_hil import validate_camera_perception_series
from .profile import RCLValidationError


class CameraFrameReader(Protocol):
    def __call__(self) -> tuple[Any, str]:
        """Return (frame, frame_ref). frame_ref must point to retained evidence."""


class CameraSemanticInferencer(Protocol):
    def __call__(self, frame: Any) -> dict[str, Any]:
        """Return semantic_state, predicate, confidence and optional evidence refs."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def collect_camera_perception_series(
    frame_reader: CameraFrameReader,
    inferencer: CameraSemanticInferencer,
    *,
    series_id: str,
    robot_id: str,
    camera_component_id: str,
    model_id: str,
    runtime: str,
    model_version: str | None = None,
    sessions: int = 3,
    trials_per_session: int = 3,
    clock: Callable[[], str] = _now,
) -> dict[str, Any]:
    """Collect a camera-perception-series from deployment-provided readers."""

    if sessions < 1 or trials_per_session < 1:
        raise RCLValidationError("sessions and trials_per_session must be >= 1")

    output_sessions: list[dict[str, Any]] = []
    for session_index in range(1, sessions + 1):
        started_at = clock()
        trials: list[dict[str, Any]] = []
        for trial_index in range(1, trials_per_session + 1):
            frame, frame_ref = frame_reader()
            if not isinstance(frame_ref, str) or not frame_ref.strip():
                raise RCLValidationError("camera frame_reader must return a non-empty frame_ref")

            inference = dict(inferencer(frame))
            required = {"semantic_state", "predicate", "confidence"}
            missing = sorted(required - inference.keys())
            if missing:
                raise RCLValidationError(
                    f"camera inferencer missing required fields: {', '.join(missing)}"
                )
            confidence = float(inference["confidence"])
            if not 0 <= confidence <= 1:
                raise RCLValidationError("camera inference confidence must be between 0 and 1")
            if not isinstance(inference["predicate"], bool):
                raise RCLValidationError("camera inference predicate must be boolean")

            trial_id = f"{series_id}-s{session_index:02d}-t{trial_index:02d}"
            item = {
                "inference_id": f"{trial_id}-inference",
                "semantic_state": str(inference["semantic_state"]),
                "predicate": inference["predicate"],
                "confidence": confidence,
                "evidence_refs": list(inference.get("evidence_refs", [])),
            }
            if inference.get("strategy_id"):
                item["strategy_id"] = str(inference["strategy_id"])

            trials.append(
                {
                    "trial_id": trial_id,
                    "captured_at": clock(),
                    "frame_ref": frame_ref,
                    "inferences": [item],
                }
            )
        output_sessions.append(
            {
                "session_id": f"{series_id}-session-{session_index:02d}",
                "started_at": started_at,
                "trials": trials,
            }
        )

    model: dict[str, str] = {"model_id": model_id, "runtime": runtime}
    if model_version:
        model["version"] = model_version

    series = {
        "camera_perception_series_version": "0.1",
        "series_id": series_id,
        "robot_id": robot_id,
        "sensor_component_id": camera_component_id,
        "model": model,
        "evidence_refs": [],
        "sessions": output_sessions,
    }
    validate_camera_perception_series(series)
    return series


def build_opencv_frame_reader(
    source: int | str,
    *,
    evidence_dir: str | Path,
    jpeg_quality: int = 95,
) -> tuple[CameraFrameReader, Callable[[], None]]:
    """Build an optional OpenCV reader for V4L2 or GStreamer camera sources."""

    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RCLValidationError(
            "OpenCV camera deployment requires opencv-python or a platform OpenCV build"
        ) from exc

    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        capture.release()
        raise RCLValidationError(f"camera source could not be opened: {source!r}")

    evidence_path = Path(evidence_dir)
    evidence_path.mkdir(parents=True, exist_ok=True)
    counter = 0

    def reader() -> tuple[Any, str]:
        nonlocal counter
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RCLValidationError("camera capture failed")
        counter += 1
        frame_path = evidence_path / f"frame-{counter:06d}.jpg"
        ok = cv2.imwrite(
            str(frame_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
        )
        if not ok:
            raise RCLValidationError(f"failed to persist camera evidence: {frame_path}")
        return frame, frame_path.resolve().as_uri()

    return reader, capture.release
