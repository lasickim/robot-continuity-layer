from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cli import main as legacy_main
from .experience import compact_experience
from .habit_approval import apply_habit_approval, preview_habit_approval
from .intent_approval_cli import run as run_intent_approval
from .intent_discovery import (
    discover_intent_candidate,
    load_default_intent_discovery_policy,
)
from .intent_revision_cli import run as run_intent_revision
from .intent_summary_discovery_cli import run as run_intent_summary_discovery
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


def _discovery_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl discover-intent")
    parser.add_argument("dataset")
    parser.add_argument("--policy")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def _run_discovery(argv: list[str]) -> int:
    args = _discovery_parser().parse_args(argv)
    dataset = _read_json(args.dataset)
    policy = _read_json(args.policy) if args.policy else load_default_intent_discovery_policy()
    report = discover_intent_candidate(dataset, policy=policy)

    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        evidence = report["evidence"]
        hypothesis = report["hypothesis"]
        intent = hypothesis["proposed_intent"]
        print("RCL Intent Discovery")
        print(f"Dataset: {report['dataset_id']}")
        print(f"Candidate ID: {report['candidate_id']}")
        print(f"Action: {hypothesis['candidate_action_id']}")
        print(f"Proposed Goal: {intent['goal_id']}")
        print(f"Context: {hypothesis['context_match']}")
        print("Evidence Basis: RAW")
        print(
            "Samples: "
            f"context={evidence['context_episode_count']} "
            f"present={evidence['action_present_count']} "
            f"absent={evidence['action_absent_count']} "
            f"ignored={evidence['ignored_episode_count']}"
        )
        repeat = evidence["action_repeat_rate"]
        print(f"Action Repeat Rate: {'N/A' if repeat is None else f'{repeat:.3f}'}")
        print(
            "Outcome Means: "
            f"present={evidence['action_present_mean']} "
            f"absent={evidence['action_absent_mean']}"
        )
        print(
            "Beneficial Effect: "
            f"{evidence['beneficial_effect']} "
            f"(required >= {evidence['minimum_meaningful_effect']})"
        )
        print(f"Status: {report['status']}")
        print(f"Confidence: {report['confidence']}")
        print("Causal Claim: NO")
        print(f"Next: {report['recommended_next_action']}")
        failed = [gate for gate in report["gates"] if not gate["passed"]]
        for gate in failed:
            print(
                f"- BLOCK {gate['gate']}: actual={gate['actual']!r} "
                f"required={gate['required']!r}"
            )

    return 0 if report["status"] == "candidate" else 7


def _experience_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl compact-experience")
    parser.add_argument("source")
    parser.add_argument("--output")
    parser.add_argument("--retained-exemplars", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    return parser


def _run_experience(argv: list[str]) -> int:
    args = _experience_parser().parse_args(argv)
    source = _read_json(args.source)
    summary = compact_experience(source, retained_exemplars=args.retained_exemplars)

    if args.output:
        print(_write_json(args.output, summary))
    elif args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("RCL Experience Compaction")
        print(f"Store: {summary['source']['store_id']}")
        print(f"Episodes: {summary['source']['episode_count']}")
        print(f"Groups: {summary['group_count']}")
        print("Destructive: NO")
        for group in summary["groups"]:
            print(
                f"- {group['action_id']} context={group['context']} "
                f"episodes={group['episode_count']} present={group['action_present_count']} "
                f"absent={group['action_absent_count']}"
            )
            for outcome_id, stats in group["outcomes"].items():
                if stats["type"] == "numeric":
                    print(
                        f"    {outcome_id}: numeric n={stats['count']} mean={stats['mean']} "
                        f"std={stats['sample_std']} range=[{stats['min']}, {stats['max']}]"
                    )
                else:
                    print(
                        f"    {outcome_id}: binary n={stats['count']} "
                        f"true_rate={stats['true_rate']}"
                    )
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "approve-habit":
        try:
            return _run_approval(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "approve-intent":
        try:
            return run_intent_approval(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "revise-intent":
        try:
            return run_intent_revision(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "discover-intent-summary":
        try:
            return run_intent_summary_discovery(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "discover-intent":
        try:
            return _run_discovery(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "compact-experience":
        try:
            return _run_experience(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    return legacy_main()


if __name__ == "__main__":
    raise SystemExit(main())
