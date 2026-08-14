from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .example_adapter import ExampleMobileBaseAdapter
from .migration import migrate_profile
from .profile import RCLProfile, RCLValidationError, validate_schema


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="rcl")
    sub = parser.add_subparsers(dest="command", required=True)
    p_validate = sub.add_parser("validate"); p_validate.add_argument("path"); p_validate.set_defaults(func=_cmd_validate)
    p_inspect = sub.add_parser("inspect"); p_inspect.add_argument("path"); p_inspect.set_defaults(func=_cmd_inspect)
    p_pack = sub.add_parser("pack"); p_pack.add_argument("source"); p_pack.add_argument("output"); p_pack.add_argument("--profile-id", default="RCL-DEMO-PROFILE-001"); p_pack.set_defaults(func=_cmd_pack)
    p_migrate = sub.add_parser("migrate"); p_migrate.add_argument("source"); p_migrate.add_argument("target_embodiment"); p_migrate.add_argument("--adapter", default="example-mobile-base"); p_migrate.add_argument("--output"); p_migrate.set_defaults(func=_cmd_migrate)
    p_report = sub.add_parser("report"); p_report.add_argument("path"); p_report.set_defaults(func=_cmd_report)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (RCLValidationError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
