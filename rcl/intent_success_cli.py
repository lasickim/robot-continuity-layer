from __future__ import annotations

import argparse
import json
from pathlib import Path

from .intent_success_evaluation import evaluate_observed_intent_success
from .profile import RCLProfile


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rcl evaluate-intent")
    parser.add_argument("profile")
    parser.add_argument("observations")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate_observed_intent_success(
        RCLProfile.open(args.profile),
        _read_json(args.observations),
    )

    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("RCL Observed Intent Success")
        print(f"Observed Robot: {report['observed_subject']['robot_id']}")
        print(f"Observed Embodiment: {report['observed_subject']['embodiment_id']}")
        print(f"Status: {report['status']}")
        for result in report["intent_results"]:
            strategy = result["strategy_id"] or "(not recorded)"
            print(
                f"- {result['behavior_id']} [{result['criticality']}] "
                f"{result['status'].upper()} strategy={strategy}"
            )
            print(f"  goal={result['goal_id']}")
            print(f"  success_condition={result['success_condition']}")
        if report["required_failures"]:
            print("Required Failures: " + ", ".join(report["required_failures"]))
        if report["required_inconclusive"]:
            print("Required Inconclusive: " + ", ".join(report["required_inconclusive"]))
        if report["nonblocking_failures"]:
            print("Nonblocking Failures: " + ", ".join(report["nonblocking_failures"]))
        print("Motion Similarity Used: NO")
        print("Safety Certification: NO")

    return 0 if report["status"] == "passed" else (7 if report["status"] == "inconclusive" else 8)
