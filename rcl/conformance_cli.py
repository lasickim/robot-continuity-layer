from __future__ import annotations

import argparse
import importlib
import json
from typing import Any

from .conformance import run_adapter_conformance
from .intent_conformance import run_intent_adapter_conformance


def load_adapter(spec: str):
    module_name, sep, object_path = spec.partition(":")
    if not sep or not module_name or not object_path:
        raise ValueError("Adapter must use module.path:AdapterClass syntax")

    module = importlib.import_module(module_name)
    obj: Any = module
    for part in object_path.split("."):
        obj = getattr(obj, part)

    if not isinstance(obj, type):
        raise ValueError("Adapter target must resolve to a class")
    return obj()


def _group_order(report: dict[str, Any]) -> list[str]:
    if report["suite_id"] == "rcl.adapter.intent.v0.4":
        return ["Profile", "Adapter", "Intent", "Paths", "Safety", "Reporting"]
    return ["Profile", "Adapter", "Migration", "Safety", "Reporting"]


def _print_text(report: dict[str, Any]) -> None:
    print("RCL Adapter Conformance")
    print(f"Suite: {report['suite_id']} ({report['suite_version']})")
    print(
        "Adapter: "
        f"{report['adapter']['adapter_id']} "
        f"{report['adapter']['adapter_version']}"
    )
    print()
    for group in _group_order(report):
        print(f"{group:<12} {'PASS' if report['groups'][group] else 'FAIL'}")

    failed = [item for item in report["checks"] if not item["passed"]]
    if failed:
        print("\nFailed checks:")
        for item in failed:
            print(f"- {item['check_id']}: {item['message']}")

    print()
    if report["passed"]:
        print(f"Result: {report['compatibility_level']} (experimental suite {report['suite_version']})")
    else:
        print("Result: NOT CONFORMANT")


def main() -> int:
    parser = argparse.ArgumentParser(prog="rcl-conformance")
    sub = parser.add_subparsers(dest="command", required=True)

    test = sub.add_parser("test", help="run the experimental v0.3 mobile-base adapter conformance suite")
    test.add_argument("adapter", help="Python adapter class as module.path:AdapterClass")
    test.add_argument("--json", action="store_true", dest="json_output", help="emit JSON only")

    intent = sub.add_parser("intent", help="run the experimental v0.4 Intent-aware adapter conformance suite")
    intent.add_argument("adapter", help="Python adapter class as module.path:AdapterClass")
    intent.add_argument("--json", action="store_true", dest="json_output", help="emit JSON only")

    args = parser.parse_args()

    try:
        adapter = load_adapter(args.adapter)
        if args.command == "intent":
            report = run_intent_adapter_conformance(adapter)
        else:
            report = run_adapter_conformance(adapter)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        if getattr(args, "json_output", False):
            print(json.dumps({"passed": False, "error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}")
        return 2

    if args.json_output:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)
    return 0 if report["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
