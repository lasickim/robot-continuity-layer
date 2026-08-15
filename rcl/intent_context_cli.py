from __future__ import annotations

import argparse
import json
from pathlib import Path

from .intent_context_report import (
    diagnose_intent_context,
    diagnose_intent_context_from_summary,
)


def _read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def _print(report):
    diagnostic = report["diagnostics"]
    print("RCL Intent Context Diagnostics")
    print(f"Dataset: {report['dataset_id']}")
    print(f"Candidate: {report['candidate_id']} [{report['candidate_status']}]")
    print(f"Evidence Basis: {report['evidence_basis'].upper()}")
    print(f"Status: {diagnostic['status'].upper()}")
    print(f"Review Required: {'YES' if diagnostic['review_required'] else 'NO'}")
    if not diagnostic["fields"]:
        print("Residual Context Fields: NONE")
    for field in diagnostic["fields"]:
        print(
            f"- {field['field']}: {field['status']} "
            f"values={field['value_count']} supported={field['supported_value_count']}"
        )
        if field["action_prevalence_signal"]:
            print(f"  action-repeat spread={field['action_repeat_rate_spread']} [CAUTION]")
        if field["effect_heterogeneity_signal"]:
            print(f"  effect spread={field['beneficial_effect_spread']} [CAUTION]")
        for stratum in field["strata"]:
            print(
                f"  value={stratum['value']!r} "
                f"present={stratum['action_present_count']} absent={stratum['action_absent_count']} "
                f"effect={stratum['beneficial_effect']} direction={stratum['effect_direction']}"
            )
    for warning in diagnostic["warnings"]:
        print(f"WARNING: {warning}")
    print("Causal Claim: NO")
    print("Candidate Mutation: NO")


def run_raw(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rcl diagnose-intent-context")
    parser.add_argument("dataset")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose_intent_context(_read_json(args.dataset))
    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print(report)
    return 7 if report["diagnostics"]["review_required"] else 0


def run_summary(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rcl diagnose-intent-context-summary")
    parser.add_argument("summary")
    parser.add_argument("hypothesis")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose_intent_context_from_summary(
        _read_json(args.summary),
        _read_json(args.hypothesis),
    )
    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print(report)
    return 7 if report["diagnostics"]["review_required"] else 0
