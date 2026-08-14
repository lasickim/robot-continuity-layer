from __future__ import annotations

import argparse
import json
from pathlib import Path

from .intent_discovery import (
    discover_intent_candidate_from_summary,
    load_default_intent_discovery_policy,
)


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl discover-intent-summary")
    parser.add_argument("summary")
    parser.add_argument("hypothesis")
    parser.add_argument("--policy")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    summary = _read_json(args.summary)
    hypothesis = _read_json(args.hypothesis)
    policy = _read_json(args.policy) if args.policy else load_default_intent_discovery_policy()
    report = discover_intent_candidate_from_summary(summary, hypothesis, policy=policy)

    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        evidence = report["evidence"]
        provenance = report["evidence_provenance"]
        print("RCL Summary-Aware Intent Discovery")
        print(f"Dataset: {report['dataset_id']}")
        print(f"Candidate ID: {report['candidate_id']}")
        print(f"Action: {report['hypothesis']['candidate_action_id']}")
        print(f"Proposed Goal: {report['hypothesis']['proposed_intent']['goal_id']}")
        print("Evidence Basis: AGGREGATE")
        print(f"Summary: {provenance['summary_id']}")
        print(f"Store: {provenance['store_id']}")
        print(f"Contributing Groups: {len(provenance['group_ids'])}")
        print(
            "Samples: "
            f"context={evidence['context_episode_count']} "
            f"present={evidence['action_present_count']} "
            f"absent={evidence['action_absent_count']} "
            f"ignored={evidence['ignored_episode_count']}"
        )
        print(
            "Outcome Means: "
            f"present={evidence['action_present_mean']} "
            f"absent={evidence['action_absent_mean']}"
        )
        print(f"Beneficial Effect: {evidence['beneficial_effect']}")
        print(f"Status: {report['status']}")
        print(f"Confidence: {report['confidence']}")
        print("Causal Claim: NO")
        print(f"Next: {report['recommended_next_action']}")
        for gate in report["gates"]:
            if not gate["passed"]:
                print(
                    f"- BLOCK {gate['gate']}: actual={gate['actual']!r} "
                    f"required={gate['required']!r}"
                )

    return 0 if report["status"] == "candidate" else 7
