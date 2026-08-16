from __future__ import annotations

import argparse
import json
from pathlib import Path

from rcl.camera_deployment import (
    build_opencv_frame_reader,
    collect_camera_perception_series,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture real camera frames and build an RCL camera-perception-series."
    )
    parser.add_argument("--source", default="0", help="OpenCV source index or GStreamer pipeline")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--camera-component-id", required=True)
    parser.add_argument("--model-id", default="manual-clearance-demo")
    parser.add_argument("--runtime", default="manual-demo")
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument("--trials-per-session", type=int, default=3)
    args = parser.parse_args()

    source: int | str = int(args.source) if args.source.isdigit() else args.source
    reader, close_camera = build_opencv_frame_reader(
        source,
        evidence_dir=args.evidence_dir,
    )

    # This producer example intentionally uses a placeholder inferencer. Replace
    # it on Jetson with YOLO/TensorRT/CV/VLM logic that returns a real predicate
    # and calibrated confidence for the declared semantic state.
    def inferencer(frame):
        raise RuntimeError(
            "Replace inferencer() with the deployment perception runtime before collecting evidence."
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
