from __future__ import annotations

import argparse
import json
from pathlib import Path

from .intent_revision import apply_intent_revision, preview_intent_revision
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
    parser = argparse.ArgumentParser(prog="rcl revise-intent")
    sub = parser.add_subparsers(dest="revision_command", required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("source")
    preview.add_argument("revision_candidate")
    preview.add_argument("behavior_id")
    preview.add_argument("--approved-at", required=True)
    preview.add_argument("--approved-by")
    preview.add_argument("--output")
    preview.add_argument("--json", action="store_true")

    apply = sub.add_parser("apply")
    apply.add_argument("source")
    apply.add_argument("revision_candidate")
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
    candidate = _read_json(args.revision_candidate)

    if args.revision_command == "preview":
        patch = preview_intent_revision(
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
            print("RCL Intent Revision Preview")
            print(f"Behavior: {patch['behavior_id']}")
            print(f"From Goal: {patch['before_intent']['goal_id']}")
            print(f"To Goal: {patch['after_intent']['goal_id']}")
            print(f"Revision: {patch['history_entry']['revision_id']}")
            print(f"Reason: {patch['candidate']['reason']}")
            print(f"Approved At: {patch['approved_at']}")
            print(f"Approved By: {patch['approved_by'] or '(not recorded)'}")
            print("Causal Claim: NO")
            print("No profile files were modified.")
        return 0

    result = apply_intent_revision(
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
        print("RCL Intent Revision Applied")
        print(f"Behavior: {result['behavior_id']}")
        print(f"Revision: {result['revision_id']}")
        print(f"Output Profile ID: {result['output_profile_id']}")
        print(f"Output: {result['output_path']}")
        print("Previous Intent Preserved: YES")
        print("Source Unchanged: YES")
        print("Output Valid: YES")
        print("Causal Claim: NO")
    return 0
