from __future__ import annotations

import argparse
import json
from pathlib import Path

from rcl import (
    CapabilityPathReferenceAdapter,
    RCLProfile,
    build_hil_runtime_attestation,
    run_hil_reference_experiment,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the v0.5 HIL semantic reference on a declared edge execution host."
    )
    parser.add_argument("--component-id", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument(
        "--deployment",
        action="store_true",
        help="Explicitly declare that this process is running on the intended HIL deployment host.",
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    root = _root()
    base = root / "examples" / "v0.5-sim"
    attestation = build_hil_runtime_attestation(
        component_id=args.component_id,
        environment="deployment" if args.deployment else "unclassified",
        real_roles=("compute",),
        simulated_roles=("plant",),
        evidence_refs=tuple(args.evidence_ref),
    )
    report = run_hil_reference_experiment(
        RCLProfile.open(base / "robot-a"),
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _read(base / "robot-b.intent-series.json"),
        CapabilityPathReferenceAdapter(),
        attestation,
        behavior_id="safety.pre_sit_clearance_check",
        expected_target_path_id="direct_clearance",
    )

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    return 0 if report["assertions"]["experiment_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
