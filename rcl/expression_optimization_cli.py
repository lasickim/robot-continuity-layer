from __future__ import annotations

import argparse
import json
from pathlib import Path

from .expression_optimization import (
    apply_expression_optimization,
    preview_expression_optimization,
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
    parser = argparse.ArgumentParser(prog="rcl optimize-expression")
    sub = parser.add_subparsers(dest="command", required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("source")
    preview.add_argument("candidate")
    preview.add_argument("behavior_id")
    preview.add_argument("--approved-at", required=True)
    preview.add_argument("--approved-by")
    preview.add_argument("--output")
    preview.add_argument("--json", action="store_true")

    apply = sub.add_parser("apply")
    apply.add_argument("source")
    apply.add_argument("candidate")
    apply.add_argument("behavior_id")
    apply.add_argument("output_dir")
    apply.add_argument("--approved-at", required=True)
    apply.add_argument("--approved-by")
    apply.add_argument("--profile-id")
    apply.add_argument("--json", action="store_true")
    return parser


def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    profile = RCLProfile.open(args.source)
    candidate = _read_json(args.candidate)

    if args.command == "preview":
        patch = preview_expression_optimization(
            profile,
            candidate,
            args.behavior_id,
            approved_at=args.approved_at,
            approved_by=args.approved_by,
        )
        if args.output:
            print(_write_json(args.output, patch))
        elif args.json:
            print(json.dumps(patch, indent=2, ensure_ascii=False))
        else:
            print("RCL Expression Optimization Preview")
            print(f"Behavior: {patch['behavior_id']}")
            print(f"Action: {patch['candidate']['action']}")
            print(f"Candidate: {patch['candidate']['candidate_id']}")
            print(f"Approved At: {patch['approved_at']}")
            print(f"Approved By: {patch['approved_by'] or '(not recorded)'}")
            print(f"History Entry: {patch['history_entry']['optimization_id']}")
            print("No profile files were modified.")
        return 0

    result = apply_expression_optimization(
        profile,
        candidate,
        args.behavior_id,
        args.output_dir,
        approved_at=args.approved_at,
        approved_by=args.approved_by,
        output_profile_id=args.profile_id,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("RCL Expression Optimization Applied")
        print(f"Behavior: {result['behavior_id']}")
        print(f"Action: {result['action']}")
        print(f"Output Profile ID: {result['output_profile_id']}")
        print(f"Output: {result['output_path']}")
        print("Source Unchanged: YES")
        print("Output Valid: YES")
    return 0
