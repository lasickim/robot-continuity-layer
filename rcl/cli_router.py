from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cli import main as legacy_main
from .habit_approval import apply_habit_approval, preview_habit_approval
from .profile import RCLProfile, RCLValidationError


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def _approval_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl approve-habit")
    sub = parser.add_subparsers(dest="approval_command", required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("source")
    preview.add_argument("promotion_report")
    preview.add_argument("behavior_id")
    preview.add_argument("--approved-at", required=True)
    preview.add_argument("--approved-by")
    preview.add_argument("--output")
    preview.add_argument("--json", action="store_true")

    apply = sub.add_parser("apply")
    apply.add_argument("source")
    apply.add_argument("promotion_report")
    apply.add_argument("behavior_id")
    apply.add_argument("output_dir")
    apply.add_argument("--approved-at", required=True)
    apply.add_argument("--approved-by")
    apply.add_argument("--profile-id")
    apply.add_argument("--json", action="store_true")
    return parser


def _run_approval(argv: list[str]) -> int:
    args = _approval_parser().parse_args(argv)
    profile = RCLProfile.open(args.source)
    report = _read_json(args.promotion_report)

    if args.approval_command == "preview":
        patch = preview_habit_approval(
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
            print("RCL Habit Approval Preview")
            print(f"Behavior: {patch['behavior_id']}")
            print(f"Transition: {patch['from_lifecycle']} -> {patch['to_lifecycle']}")
            print(f"Approved At: {patch['approved_at']}")
            print(f"Approved By: {patch['approved_by'] or '(not recorded)'}")
            print("Changes:")
            for change in patch["changes"]:
                print(f"- {change['path']}: {change['before']!r} -> {change['after']!r}")
            event = patch["history_event"]
            print(f"History Event: {event['event_id']} [{event['event_type']}]")
            print("No profile files were modified.")
        return 0

    result = apply_habit_approval(
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
        print("RCL Habit Approval Applied")
        print(f"Behavior: {result['behavior_id']}")
        print(f"Transition: {result['from_lifecycle']} -> {result['to_lifecycle']}")
        print(f"Output Profile ID: {result['output_profile_id']}")
        print(f"Output: {result['output_path']}")
        print("Source Unchanged: YES")
        print("Output Valid: YES")
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "approve-habit":
        try:
            return _run_approval(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    return legacy_main()


if __name__ == "__main__":
    raise SystemExit(main())
