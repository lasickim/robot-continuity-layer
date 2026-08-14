from __future__ import annotations

import argparse
import json
from pathlib import Path

from .expression_recommendation import (
    evaluate_expression_optimization_recommendations,
    load_default_expression_optimization_policy,
)
from .profile import RCLProfile


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl expression-recommendations")
    parser.add_argument("profile")
    parser.add_argument("migration_report")
    parser.add_argument("intent_success_report")
    parser.add_argument("--policy")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    profile = RCLProfile.open(args.profile)
    migration_report = _read_json(args.migration_report)
    intent_success_report = _read_json(args.intent_success_report)
    policy = (
        _read_json(args.policy)
        if args.policy
        else load_default_expression_optimization_policy()
    )
    report = evaluate_expression_optimization_recommendations(
        profile,
        migration_report,
        intent_success_report,
        policy=policy,
    )

    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("RCL Expression Optimization Recommendations")
        print(f"Policy: {report['policy']['policy_id']}")
        print(f"Target: {report['target']['embodiment_id']}")
        print("Mutation: NO")
        print("Redundancy Proven: NO")
        for item in report["recommendations"]:
            print(
                f"- {item['behavior_id']}: {item['decision']} "
                f"[{item['preservation_priority']}/{item['legacy_significance']}]"
            )
            print(f"  Expression: {item['expression_id']}")
            print(f"  Target Strategy: {item['intent_evidence']['target_strategy']}")
            print(f"  Observed Intent: {item['intent_evidence']['observed_status']}")
            print(f"  Next: {item['recommended_next_action']}")
            print(f"  Reason: {item['reason']}")

    return 0
