from pathlib import Path

import pytest

from rcl.camera_deployment import collect_camera_perception_series
from rcl.profile import RCLValidationError


def _clock():
    values = iter(
        [
            "2026-08-16T14:30:00Z",
            "2026-08-16T14:30:01Z",
            "2026-08-16T14:30:02Z",
            "2026-08-16T14:31:00Z",
            "2026-08-16T14:31:01Z",
            "2026-08-16T14:31:02Z",
            "2026-08-16T14:32:00Z",
        ]
    )
    return lambda: next(values)


def test_collect_camera_perception_series_from_injected_runtime():
    frames = iter([("frame-a", "file:///evidence/a.jpg"), ("frame-b", "file:///evidence/b.jpg"), ("frame-c", "file:///evidence/c.jpg"), ("frame-d", "file:///evidence/d.jpg")])

    series = collect_camera_perception_series(
        lambda: next(frames),
        lambda frame: {
            "semantic_state": "state.sitting_area_clear",
            "predicate": True,
            "confidence": 0.91,
            "strategy_id": "target.camera_clearance",
            "evidence_refs": [f"file:///inference/{frame}.json"],
        },
        series_id="camera-live-demo",
        robot_id="robot-b",
        camera_component_id="camera-01",
        model_id="clearance-demo",
        runtime="mock-runtime",
        sessions=2,
        trials_per_session=2,
        clock=_clock(),
    )

    assert series["sensor_component_id"] == "camera-01"
    assert series["model"]["model_id"] == "clearance-demo"
    assert series["sessions"][0]["trials"][0]["frame_ref"] == "file:///evidence/a.jpg"
    inference = series["sessions"][1]["trials"][1]["inferences"][0]
    assert inference["predicate"] is True
    assert inference["confidence"] == 0.91
    assert inference["strategy_id"] == "target.camera_clearance"


def test_camera_deployment_requires_retained_frame_reference():
    with pytest.raises(RCLValidationError, match="frame_ref"):
        collect_camera_perception_series(
            lambda: (object(), ""),
            lambda frame: {
                "semantic_state": "state.sitting_area_clear",
                "predicate": True,
                "confidence": 1.0,
            },
            series_id="bad-frame-ref",
            robot_id="robot-b",
            camera_component_id="camera-01",
            model_id="demo",
            runtime="mock",
            sessions=1,
            trials_per_session=1,
        )


def test_camera_deployment_rejects_invalid_inference_shape():
    with pytest.raises(RCLValidationError, match="missing required fields"):
        collect_camera_perception_series(
            lambda: (object(), "file:///frame.jpg"),
            lambda frame: {"semantic_state": "state.sitting_area_clear"},
            series_id="bad-inference",
            robot_id="robot-b",
            camera_component_id="camera-01",
            model_id="demo",
            runtime="mock",
            sessions=1,
            trials_per_session=1,
        )
