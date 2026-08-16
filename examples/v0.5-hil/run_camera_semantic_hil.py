from __future__ import annotations

import argparse
import json
from pathlib import Path

from rcl.camera_semantic_hil import run_camera_semantic_hil_experiment
from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.profile import RCLProfile


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.5 Camera Semantic HIL.")
    parser.add_argument("--perception-series", required=True)
    parser.add_argument("--edge-component-id", required=True)
    parser.add_argument("--camera-component-id", required=True)
    parser.add_argument("--minimum-confidence", type=float, required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--deployment", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = _root()
    base = root / "examples" / "v0.5-sim"
    report = run_camera_semantic_hil_experiment(
        RCLProfile.open(base / "robot-a"),
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _read(Path(args.perception_series)),
        CapabilityPathReferenceAdapter(),
        edge_component_id=args.edge_component_id,
        camera_component_id=args.camera_component_id,
        behavior_id="safety.pre_sit_clearance_check",
        trigger="activity.before_sit_down",
        success_condition="state.sitting_area_clear",
        semantic_state="state.sitting_area_clear",
        default_strategy_id="target.direct_clearance_state",
        minimum_confidence=args.minimum_confidence,
        evidence_refs=tuple(args.evidence_ref),
        deployment=args.deployment,
        expected_target_path_id="direct_clearance",
    )

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    return 0 if report["experiment_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
