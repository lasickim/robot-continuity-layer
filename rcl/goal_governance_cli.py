from __future__ import annotations

import argparse
import json
from pathlib import Path

from .goal_governance import record_goal_proposal_decision, review_goal_proposal


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def run_review(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rcl review-goal-proposal")
    parser.add_argument("proposal")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = review_goal_proposal(_read_json(args.proposal))
    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("RCL Goal Vocabulary Proposal Review")
        print(f"Proposal: {report['proposal_id']}")
        print(f"Goal: {report['proposed_goal_id']}")
        print(f"Status: {report['status'].upper()}")
        print(f"Eligible For Approval: {'YES' if report['eligible_for_approval'] else 'NO'}")
        print(f"Recommended Decision: {report['recommended_decision'].upper()}")
        if report["blockers"]:
            print("Blockers: " + ", ".join(report["blockers"]))
        if report["advisories"]:
            print("Advisories: " + ", ".join(report["advisories"]))
        if report["overlap_candidates"]:
            top = report["overlap_candidates"][0]
            print(f"Top Semantic Overlap: {top['goal_id']} ({top['token_overlap']:.3f})")
        if report["specificity_hits"]:
            hits = ", ".join(
                f"{item['field']}:{item['term']}" for item in report["specificity_hits"]
            )
            print("Body-Specificity Signals: " + hits)
        print("Vocabulary Mutated: NO")

    return 8 if report["status"] == "blocked" else (7 if report["status"] == "needs_revision" else 0)


def run_decision(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rcl decide-goal-proposal")
    parser.add_argument("proposal")
    parser.add_argument("review_report")
    parser.add_argument("--decision", required=True, choices=["approved", "rejected", "needs_revision"])
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    record = record_goal_proposal_decision(
        _read_json(args.proposal),
        _read_json(args.review_report),
        decision=args.decision,
        reviewed_at=args.reviewed_at,
        reviewed_by=args.reviewed_by,
        reason=args.reason,
    )
    if args.output:
        print(_write_json(args.output, record))
    elif args.json:
        print(json.dumps(record, indent=2, ensure_ascii=False))
    else:
        print("RCL Goal Vocabulary Decision")
        print(f"Decision ID: {record['decision_id']}")
        print(f"Proposal: {record['proposal_id']}")
        print(f"Decision: {record['decision'].upper()}")
        print(f"Review Status: {record['review_status'].upper()}")
        print(f"Reviewed By: {record['reviewed_by']}")
        print(f"Next Action: {record['next_action']}")
        print("Vocabulary Mutated: NO")
    return 0
