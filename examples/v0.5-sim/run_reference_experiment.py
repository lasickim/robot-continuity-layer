from __future__ import annotations

import json
from pathlib import Path

from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.profile import RCLProfile
from rcl.simulation_reference import run_simulation_reference_experiment


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "examples" / "v0.5-sim"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    profile = RCLProfile.open(BASE / "robot-a")
    report = run_simulation_reference_experiment(
        profile,
        _read_json(BASE / "robot-b.embodiment.json"),
        _read_json(BASE / "robot-a.intent-series.json"),
        _read_json(BASE / "robot-b.intent-series.json"),
        CapabilityPathReferenceAdapter(),
        behavior_id="safety.pre_sit_clearance_check",
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T04:00:00Z",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["assertions"]["experiment_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
