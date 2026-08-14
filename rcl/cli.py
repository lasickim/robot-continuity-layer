from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .capabilities import (
    CapabilityValidationError,
    classify_capability_id,
    load_capability_registry,
    registered_capabilities,
    validate_capability_id,
)
from .evaluation import evaluate_observed_continuity
from .example_adapter import ExampleMobileBaseAdapter
from .habit_policy import (
    evaluate_habit_promotion_candidates,
    load_default_habit_promotion_policy,
)
from .migration import migrate_profile
from .profile import RCLProfile, RCLValidationError, validate_schema
from .profile_diff import diff_profiles
from .session_evaluation import evaluate_repeated_sessions
from .statistical_evaluation import compare_trial_distributions


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_or_print_json(report, output: str | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))


def _cmd_validate(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.path)
    print("VALID")
    print(json.dumps(profile.summary(), indent=2, ensure_ascii=False))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.path)
    print(json.dumps(profile.summary(), indent=2, ensure_ascii=False))
    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output = RCLProfile.pack(args.source, args.output, args.profile_id, created_at)
    print(output)
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.source)
    target = _read_json(args.target_embodiment)
    validate_schema(target, "embodiment")
    if args.adapter != "example-mobile-base":
        raise RCLValidationError(f"Unknown built-in adapter: {args.adapter}")
    report = migrate_profile(profile, target, ExampleMobileBaseAdapter())
    _write_or_print_json(report, args.output)
    return 0 if report["continuity"]["migration_success"] else 3


def _cmd_report(args: argparse.Namespace) -> int:
    report = _read_json(args.path)
    validate_schema(report, "migration-report")
    c = report["continuity"]
    print(f"Continuity Score: {c['score']:.2f}%")
    print(f"Migration Success: {'YES' if c['migration_success'] else 'NO'}")
    print(f"Required Failures: {len(c['required_failures'])}")
    print(f"Safety Blocks: {len(c['safety_blocks'])}")
    for item in report["behavior_results"]:
        print(f"- {item['behavior_id']}: {item['status']} (similarity={item['similarity']:.2f})")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.source)
    report = evaluate_observed_continuity(profile, _read_json(args.observations))
    if args.output:
        _write_or_print_json(report, args.output)
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Observed Continuity Score: {report['score']:.2f}%")
        print(f"Evaluation Success: {'YES' if report['evaluation_success'] else 'NO'}")
        print(f"Status: {report['status']}")
        print(f"Required Failures: {len(report['required_failures'])}")
        for item in report["metric_results"]:
            observed = "MISSING" if item["observed"] is None else item["observed"]
            similarity = "N/A" if item["similarity"] is None else f"{item['similarity']:.2f}"
            print(
                f"- {item['behavior_id']}.{item['metric_id']}: {item['status']} "
                f"(observed={observed}, target={item['target']}, similarity={similarity})"
            )
    return 0 if report["evaluation_success"] else 4


def _cmd_compare_trials(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.source)
    report = compare_trial_distributions(
        profile,
        _read_json(args.source_trials),
        _read_json(args.target_trials),
    )
    if args.output:
        _write_or_print_json(report, args.output)
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        context = report["context_comparison"]
        source_protocol = context["source_protocol"]
        target_protocol = context["target_protocol"]
        print(f"Context Comparable: {'YES' if context['compatible'] else 'NO'}")
        print(
            "Protocol: "
            f"A={source_protocol['protocol_id']}@{source_protocol['protocol_version']} "
            f"B={target_protocol['protocol_id']}@{target_protocol['protocol_version']}"
        )
        print(f"Comparison Fields: {', '.join(context['comparison_fields'])}")
        for item in context["mismatches"]:
            print(
                f"- CONTEXT MISMATCH {item['field']}: "
                f"A={item['source']!r} B={item['target']!r} ({item['reason']})"
            )
        if report["score"] is None:
            print("Statistical Continuity Score: N/A")
        else:
            print(f"Statistical Continuity Score: {report['score']:.2f}%")
        print(f"Evaluation Success: {'YES' if report['evaluation_success'] else 'NO'}")
        print(f"Status: {report['status']}")
        print(f"Required Failures: {len(report['required_failures'])}")
        for item in report["metric_results"]:
            distance = "N/A" if item["wasserstein_distance"] is None else f"{item['wasserstein_distance']:.6g}"
            similarity = "N/A" if item["similarity"] is None else f"{item['similarity']:.2f}"
            print(
                f"- {item['behavior_id']}.{item['metric_id']}: {item['status']} "
                f"(A n={item['source_count']}, B n={item['target_count']}, "
                f"W1={distance} {item['unit']}, similarity={similarity})"
            )
    return 0 if report["evaluation_success"] else 5


def _manifest_path(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def _cmd_compare_sessions(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.source)
    manifest_path = Path(args.session_manifest)
    manifest = _read_json(manifest_path)
    validate_schema(manifest, "session-manifest")
    base = manifest_path.resolve().parent
    pairs = [
        {
            "session_id": item["session_id"],
            "source_trials": _read_json(_manifest_path(base, item["source_trials"])),
            "target_trials": _read_json(_manifest_path(base, item["target_trials"])),
        }
        for item in manifest["sessions"]
    ]
    report = evaluate_repeated_sessions(profile, pairs, min_sessions=int(manifest["min_sessions"]))
    if args.output:
        _write_or_print_json(report, args.output)
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("Repeated-Session Confidence")
        print(f"Series Comparable: {'YES' if report['series_comparison']['compatible'] else 'NO'}")
        print(
            "Sessions: "
            f"total={report['total_session_count']} "
            f"scorable={report['scorable_session_count']} "
            f"successful={report['successful_session_count']} "
            f"failed={report['failed_session_count']}"
        )
        if report["mean_score"] is None:
            print("Mean Statistical Continuity Score: N/A")
        else:
            print(f"Mean Statistical Continuity Score: {report['mean_score']:.2f}%")
        if report["score_std"] is None:
            print("Between-Session Std: N/A")
        else:
            print(f"Between-Session Std: {report['score_std']:.2f}")
        ci = report["confidence_interval_95"]
        if ci is None:
            print("95% CI: N/A")
        else:
            print(
                f"95% CI: [{ci['low']:.2f}, {ci['high']:.2f}] "
                f"(half-width={ci['half_width']:.2f}, t={ci['critical_value']:.3f})"
            )
        print(f"Evaluation Success: {'YES' if report['evaluation_success'] else 'NO'}")
        print(f"Status: {report['status']}")
        for item in report["session_results"]:
            score = "N/A" if item["score"] is None else f"{item['score']:.2f}%"
            print(
                f"- {item['session_id']}: {item['status']} "
                f"(score={score}, context={'YES' if item['context_compatible'] else 'NO'})"
            )
        for item in report["series_comparison"]["mismatches"]:
            print(
                f"- SERIES MISMATCH {item['session_id']} {item['field']}: "
                f"reference={item['reference']!r} observed={item['observed']!r}"
            )
        if report["metric_summaries"]:
            print("Metric uncertainty:")
            for item in report["metric_summaries"]:
                metric_ci = item["confidence_interval_95"]
                ci_text = "N/A" if metric_ci is None else f"[{metric_ci['low']:.3f}, {metric_ci['high']:.3f}]"
                std_text = "N/A" if item["similarity_std"] is None else f"{item['similarity_std']:.3f}"
                print(
                    f"- {item['behavior_id']}.{item['metric_id']}: "
                    f"mean={item['mean_similarity']:.3f} std={std_text} 95%CI={ci_text} "
                    f"sessions={item['session_count']}"
                )
    return 0 if report["evaluation_success"] else 6


def _cmd_diff(args: argparse.Namespace) -> int:
    before = RCLProfile.open(args.before)
    after = RCLProfile.open(args.after)
    report = diff_profiles(before, after)
    if args.output:
        _write_or_print_json(report, args.output)
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        summary = report["summary"]
        print("RCL Profile Diff")
        print(
            f"Before: {report['before']['robot_id']} generation={report['before']['continuity_generation']} "
            f"embodiment={report['before']['embodiment_id']}"
        )
        print(
            f"After:  {report['after']['robot_id']} generation={report['after']['continuity_generation']} "
            f"embodiment={report['after']['embodiment_id']}"
        )
        print(f"Changed: {'YES' if report['changed'] else 'NO'}")
        print(
            "Behaviors: "
            f"+{summary['added_behaviors']} "
            f"-{summary['removed_behaviors']} "
            f"~{summary['modified_behaviors']}"
        )
        for item in report["behavior_changes"]:
            marker = {"added": "+", "removed": "-", "modified": "~"}[item["change_type"]]
            print(f"{marker} {item['behavior_id']} ({item['change_type']})")
            for change in item["parameter_changes"]:
                print(
                    f"  parameter {change['field']}: "
                    f"{change['before']!r} -> {change['after']!r}"
                )
            for change in item["field_changes"]:
                print(
                    f"  {change['field']}: "
                    f"{change['before']!r} -> {change['after']!r}"
                )
            for event in item["history_events_added"]:
                print(
                    f"  + history {event['event_id']} "
                    f"[{event['event_type']}] @ {event['observed_at']}"
                )
            for event_id in item["history_event_ids_removed"]:
                print(f"  - history {event_id}")
    return 0


def _cmd_habit_candidates(args: argparse.Namespace) -> int:
    profile = RCLProfile.open(args.source)
    session_report = _read_json(args.session_report)
    policy = _read_json(args.policy) if args.policy else load_default_habit_promotion_policy()
    report = evaluate_habit_promotion_candidates(
        profile,
        session_report,
        policy=policy,
        as_of=args.as_of,
    )
    if args.output:
        _write_or_print_json(report, args.output)
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("RCL Habit Promotion Review")
        print(f"Policy: {report['policy']['policy_id']}@{report['policy']['policy_version']}")
        print(f"As Of: {report['as_of']}")
        evidence = report["evidence_report"]
        print(
            "Evidence: "
            f"status={evidence['status']} sessions={evidence['scorable_session_count']} "
            f"mean={evidence['mean_score']} std={evidence['score_std']} "
            f"ci_half_width={evidence['score_ci_half_width']}"
        )
        print(
            f"Decisions: candidates={report['eligible_count']} "
            f"blocked={report['blocked_count']} terminal={report['terminal_count']}"
        )
        for item in report["decisions"]:
            target = item["recommended_lifecycle"] or "-"
            print(
                f"- {item['behavior_id']}: {item['current_lifecycle']} -> {target} "
                f"[{item['decision'].upper()}]"
            )
            for gate in item["gates"]:
                if not gate["passed"]:
                    print(
                        f"    BLOCK {gate['gate']}: actual={gate['actual']!r} "
                        f"required={gate['required']!r}"
                    )
    return 0


def _cmd_capabilities_list(args: argparse.Namespace) -> int:
    registry = load_capability_registry()
    capabilities = registered_capabilities()
    if args.json:
        print(json.dumps({"registry_version": registry["registry_version"], "capabilities": capabilities}, indent=2, ensure_ascii=False))
        return 0
    print(f"RCL Capability Registry v{registry['registry_version']}")
    for item in capabilities:
        print(f"- {item['capability_id']}: {item['summary']}")
    return 0


def _cmd_capabilities_show(args: argparse.Namespace) -> int:
    result = classify_capability_id(args.capability_id)
    if not result.valid:
        raise CapabilityValidationError(f"{args.capability_id}: {result.message}")
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0
    if result.kind == "standard" and result.definition is not None:
        definition = result.definition
        print(definition["capability_id"])
        print(f"Status: {definition['status']}")
        print(f"Namespace: {definition['namespace']}")
        print(f"Summary: {definition['summary']}")
        print(f"Semantics: {definition['semantics']}")
        return 0
    print(result.capability_id)
    print("Type: extension")
    print(f"Owner: {result.owner}")
    print(result.message)
    return 0


def _cmd_capabilities_validate(args: argparse.Namespace) -> int:
    result = validate_capability_id(args.capability_id, allow_extensions=not args.standard_only)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        label = "STANDARD" if result.kind == "standard" else "EXTENSION"
        print(f"VALID {label}: {result.capability_id}")
        if result.owner:
            print(f"Owner: {result.owner}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="rcl")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate"); p_validate.add_argument("path"); p_validate.set_defaults(func=_cmd_validate)
    p_inspect = sub.add_parser("inspect"); p_inspect.add_argument("path"); p_inspect.set_defaults(func=_cmd_inspect)
    p_pack = sub.add_parser("pack"); p_pack.add_argument("source"); p_pack.add_argument("output"); p_pack.add_argument("--profile-id", default="RCL-DEMO-PROFILE-001"); p_pack.set_defaults(func=_cmd_pack)
    p_migrate = sub.add_parser("migrate"); p_migrate.add_argument("source"); p_migrate.add_argument("target_embodiment"); p_migrate.add_argument("--adapter", default="example-mobile-base"); p_migrate.add_argument("--output"); p_migrate.set_defaults(func=_cmd_migrate)
    p_report = sub.add_parser("report"); p_report.add_argument("path"); p_report.set_defaults(func=_cmd_report)
    p_evaluate = sub.add_parser("evaluate"); p_evaluate.add_argument("source"); p_evaluate.add_argument("observations"); p_evaluate.add_argument("--output"); p_evaluate.add_argument("--json", action="store_true"); p_evaluate.set_defaults(func=_cmd_evaluate)
    p_trials = sub.add_parser("compare-trials"); p_trials.add_argument("source"); p_trials.add_argument("source_trials"); p_trials.add_argument("target_trials"); p_trials.add_argument("--output"); p_trials.add_argument("--json", action="store_true"); p_trials.set_defaults(func=_cmd_compare_trials)
    p_sessions = sub.add_parser("compare-sessions"); p_sessions.add_argument("source"); p_sessions.add_argument("session_manifest"); p_sessions.add_argument("--output"); p_sessions.add_argument("--json", action="store_true"); p_sessions.set_defaults(func=_cmd_compare_sessions)
    p_diff = sub.add_parser("diff"); p_diff.add_argument("before"); p_diff.add_argument("after"); p_diff.add_argument("--output"); p_diff.add_argument("--json", action="store_true"); p_diff.set_defaults(func=_cmd_diff)
    p_habit = sub.add_parser("habit-candidates"); p_habit.add_argument("source"); p_habit.add_argument("session_report"); p_habit.add_argument("--policy"); p_habit.add_argument("--as-of"); p_habit.add_argument("--output"); p_habit.add_argument("--json", action="store_true"); p_habit.set_defaults(func=_cmd_habit_candidates)

    p_capabilities = sub.add_parser("capabilities")
    capability_sub = p_capabilities.add_subparsers(dest="capability_command", required=True)
    p_cap_list = capability_sub.add_parser("list"); p_cap_list.add_argument("--json", action="store_true"); p_cap_list.set_defaults(func=_cmd_capabilities_list)
    p_cap_show = capability_sub.add_parser("show"); p_cap_show.add_argument("capability_id"); p_cap_show.add_argument("--json", action="store_true"); p_cap_show.set_defaults(func=_cmd_capabilities_show)
    p_cap_validate = capability_sub.add_parser("validate"); p_cap_validate.add_argument("capability_id"); p_cap_validate.add_argument("--standard-only", action="store_true"); p_cap_validate.add_argument("--json", action="store_true"); p_cap_validate.set_defaults(func=_cmd_capabilities_validate)

    args = parser.parse_args()
    try:
        return args.func(args)
    except (CapabilityValidationError, RCLValidationError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
