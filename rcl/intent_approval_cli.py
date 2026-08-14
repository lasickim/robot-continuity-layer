from __future__ import annotations

import argparse
import json
from pathlib import Path

from .intent_approval import apply_intent_approval, preview_intent_approval
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
    parser = argparse.ArgumentParser(prog="rcl approve-intent")
    sub = parser.add_subparsers(dest="approval_command", required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("source")
    preview.add_argument("candidate_report")
    preview.add_argument("behavior_id")
    preview.add_argument("--approved-at", required=True)
    preview.add_argument("--approved-by")
    preview.add_argument("--output")
    preview.add_argument("--json", action="store_true")

    apply = sub.add_parser("apply")
    apply.add_argument("source")
    apply.add_argument("candidate_report")
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
    report = _read_json(args.candidate_report)

    if args.approval_command == "preview":
        patch = preview_intent_approval(
            profile,
            report,
            args.behavior_id,
            approved_at=args.approved_at,
            approved_by=args.approved_by,
        )
        if args.output:
            print(_write_json(args.output, patch))
        elif args.json:
            print(json.dumps(patch, indent=2, ensure_ascii=False))
        else:
            intent = patch["after_intent"]
            print("RCL Intent Approval Preview")
            print(f"Behavior: {patch['behavior_id']}")
            print(f"Goal: {intent['goal_id']}")
            print(f"Candidate: {patch['candidate']['candidate_id']}")
            print(f"Evidence Confidence: {patch['candidate']['confidence']}")
            print(f"Approved At: {patch['approved_at']}")
            print(f"Approved By: {patch['approved_by'] or '(not recorded)'}")
            print("Causal Claim: NO")
            print("Change: behavior.intent will be added; no profile files were modified.")
        return 0

    result = apply_intent_approval(
        profile,
        report,
        args.behavior_id,
        args.output_dir,
        approved_at=args.approved_at,
        approved_by=args.approved_by,
        output_profile_id=args.profile_id,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("RCL Intent Approval Applied")
        print(f"Behavior: {result['behavior_id']}")
        print(f"Candidate: {result['candidate_id']}")
        print(f"Output Profile ID: {result['output_profile_id']}")
        print(f"Output: {result['output_path']}")
        print("Source Unchanged: YES")
        print("Output Valid: YES")
        print("Causal Claim: NO")
    return 0
