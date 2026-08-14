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
from .migration import migrate_profile
from .profile import RCLProfile, RCLValidationError, validate_schema
from .statistical_evaluation import compare_trial_distributions


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


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
    adapter = ExampleMobileBaseAdapter()
    report = migrate_profile(profile, target, adapter)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(output)
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
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
    observations = _read_json(args.observations)
    report = evaluate_observed_continuity(profile, observations)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(output)
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
    source_trials = _read_json(args.source_trials)
    target_trials = _read_json(args.target_trials)
    report = compare_trial_distributions(profile, source_trials, target_trials)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(output)
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
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

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("path")
    p_validate.set_defaults(func=_cmd_validate)

    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("path")
    p_inspect.set_defaults(func=_cmd_inspect)

    p_pack = sub.add_parser("pack")
    p_pack.add_argument("source")
    p_pack.add_argument("output")
    p_pack.add_argument("--profile-id", default="RCL-DEMO-PROFILE-001")
    p_pack.set_defaults(func=_cmd_pack)

    p_migrate = sub.add_parser("migrate")
    p_migrate.add_argument("source")
    p_migrate.add_argument("target_embodiment")
    p_migrate.add_argument("--adapter", default="example-mobile-base")
    p_migrate.add_argument("--output")
    p_migrate.set_defaults(func=_cmd_migrate)

    p_report = sub.add_parser("report")
    p_report.add_argument("path")
    p_report.set_defaults(func=_cmd_report)

    p_evaluate = sub.add_parser("evaluate")
    p_evaluate.add_argument("source")
    p_evaluate.add_argument("observations")
    p_evaluate.add_argument("--output")
    p_evaluate.add_argument("--json", action="store_true")
    p_evaluate.set_defaults(func=_cmd_evaluate)

    p_trials = sub.add_parser("compare-trials")
    p_trials.add_argument("source")
    p_trials.add_argument("source_trials")
    p_trials.add_argument("target_trials")
    p_trials.add_argument("--output")
    p_trials.add_argument("--json", action="store_true")
    p_trials.set_defaults(func=_cmd_compare_trials)

    p_capabilities = sub.add_parser("capabilities")
    capability_sub = p_capabilities.add_subparsers(dest="capability_command", required=True)

    p_cap_list = capability_sub.add_parser("list")
    p_cap_list.add_argument("--json", action="store_true")
    p_cap_list.set_defaults(func=_cmd_capabilities_list)

    p_cap_show = capability_sub.add_parser("show")
    p_cap_show.add_argument("capability_id")
    p_cap_show.add_argument("--json", action="store_true")
    p_cap_show.set_defaults(func=_cmd_capabilities_show)

    p_cap_validate = capability_sub.add_parser("validate")
    p_cap_validate.add_argument("capability_id")
    p_cap_validate.add_argument("--standard-only", action="store_true")
    p_cap_validate.add_argument("--json", action="store_true")
    p_cap_validate.set_defaults(func=_cmd_capabilities_validate)

    args = parser.parse_args()
    try:
        return args.func(args)
    except (CapabilityValidationError, RCLValidationError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
