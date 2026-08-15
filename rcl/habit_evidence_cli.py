from __future__ import annotations

import argparse
import json
from pathlib import Path

from .habit_evidence import (
    evaluate_habit_evidence_from_store,
    evaluate_habit_evidence_from_summary,
)


def _read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _context(value: str) -> dict:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("--context-json must decode to an object")
    return parsed


def _emit(report: dict, *, output: str | None, as_json: bool) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)
        return
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    metrics = report["metrics"]
    print("RCL Habit Evidence")
    print(f"Behavior: {report['behavior_id']}")
    print(f"Action: {report['action_id']}")
    print(f"Evidence Basis: {report['evidence_basis'].upper()}")
    print(f"Source Verification: {report['source_verification'].upper()}")
    print(f"Matched Groups: {metrics['matched_group_count']}")
    print(
        "Episodes: "
        f"total={metrics['episode_count']} "
        f"present={metrics['action_present_count']} "
        f"absent={metrics['action_absent_count']}"
    )
    repeat = metrics["repeat_rate"]
    span = metrics["observation_span_days"]
    print(f"Repeat Rate: {'N/A' if repeat is None else f'{repeat:.3f}'}")
    print(f"Observation Span: {'N/A' if span is None else f'{span:.3f} days'}")
    print(f"Status: {report['status'].upper()}")
    print(f"Supports Habit Review: {'YES' if report['supports_habit_review'] else 'NO'}")
    print("Pseudo Episodes Created: NO")
    print("Lifecycle Promotion Executed: NO")
    for gate in report["gates"]:
        if not gate["passed"]:
            print(f"- BLOCK {gate['gate']}: actual={gate['actual']!r} required={gate['required']!r}")


def _parser(prog: str, *, summary: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("source")
    parser.add_argument("behavior_id")
    parser.add_argument("--action-id")
    parser.add_argument("--context-json", default="{}")
    parser.add_argument("--policy")
    if summary:
        parser.add_argument("--source-store")
    parser.add_argument("--created-at")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run_raw(argv: list[str]) -> int:
    args = _parser("rcl evaluate-habit-evidence", summary=False).parse_args(argv)
    report = evaluate_habit_evidence_from_store(
        _read_json(args.source),
        args.behavior_id,
        action_id=args.action_id,
        context_match=_context(args.context_json),
        policy=_read_json(args.policy) if args.policy else None,
        created_at=args.created_at,
    )
    _emit(report, output=args.output, as_json=args.json)
    return 0 if report["supports_habit_review"] else 7


def run_summary(argv: list[str]) -> int:
    args = _parser("rcl evaluate-habit-evidence-summary", summary=True).parse_args(argv)
    report = evaluate_habit_evidence_from_summary(
        _read_json(args.source),
        args.behavior_id,
        action_id=args.action_id,
        context_match=_context(args.context_json),
        policy=_read_json(args.policy) if args.policy else None,
        source_store=_read_json(args.source_store) if args.source_store else None,
        created_at=args.created_at,
    )
    _emit(report, output=args.output, as_json=args.json)
    return 0 if report["supports_habit_review"] else 7
