from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Callable

from rcl.camera_deployment import (
    build_opencv_frame_reader,
    collect_camera_perception_series,
)


def _load_callable(spec: str) -> Callable:
    if ":" not in spec:
        raise ValueError("--inferencer must use module:function syntax")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    value = getattr(module, function_name)
    if not callable(value):
        raise TypeError(f"inferencer is not callable: {spec}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture camera frames and build an RCL camera-perception-series."
    )
    parser.add_argument("--source", default="0", help="OpenCV source index or GStreamer pipeline")
    parser.add_argument("--inferencer", required=True, help="Deployment callable as module:function")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--camera-component-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--model-version")
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument("--trials-per-session", type=int, default=3)
    args = parser.parse_args()

    source: int | str = int(args.source) if args.source.isdigit() else args.source
    inferencer = _load_callable(args.inferencer)
    reader, close_camera = build_opencv_frame_reader(
        source,
        evidence_dir=args.evidence_dir,
    )

    try:
        series = collect_camera_perception_series(
            reader,
            inferencer,
            series_id=args.series_id,
            robot_id=args.robot_id,
            camera_component_id=args.camera_component_id,
            model_id=args.model_id,
            runtime=args.runtime,
            model_version=args.model_version,
            sessions=args.sessions,
            trials_per_session=args.trials_per_session,
        )
    finally:
        close_camera()

    Path(args.output).write_text(
        json.dumps(series, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
