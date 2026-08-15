from __future__ import annotations

import argparse
import json
from pathlib import Path

from .profile import RCLProfile
from .repeated_intent_success import (
    DEFAULT_MIN_OBSERVABLE_TRIALS,
    DEFAULT_MIN_SESSIONS,
    evaluate_repeated_intent_success,
)


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _format_rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rcl evaluate-intent-series")
    parser.add_argument("profile")
    parser.add_argument("series")
    parser.add_argument(
        "--min-observable-trials",
        type=int,
        default=DEFAULT_MIN_OBSERVABLE_TRIALS,
    )
    parser.add_argument("--min-sessions", type=int, default=DEFAULT_MIN_SESSIONS)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate_repeated_intent_success(
        RCLProfile.open(args.profile),
        _read_json(args.series),
        min_observable_trials=args.min_observable_trials,
        min_sessions=args.min_sessions,
    )

    if args.output:
        print(_write_json(args.output, report))
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        subject = report["observed_subject"]
        print("RCL Repeated Intent Success")
        print(f"Series: {subject['series_id']}")
        print(f"Observed Robot: {subject['robot_id']}")
        print(f"Observed Embodiment: {subject['embodiment_id']}")
        print(
            f"Evidence: {report['total_trial_count']} trials / "
            f"{report['total_session_count']} sessions"
        )
        print(f"Status: {report['status'].upper()}")
        print()

        for summary in report["intent_summaries"]:
            interval = summary["wilson_interval_95"]
            interval_text = (
                "N/A"
                if interval is None
                else f"{interval['low'] * 100:.1f}%..{interval['high'] * 100:.1f}%"
            )
            print(
                f"- {summary['behavior_id']} [{summary['criticality']}] "
                f"{summary['status'].upper()}"
            )
            print(f"  goal={summary['goal_id']}")
            print(
                "  observed="
                f"{summary['pass_count']} pass / {summary['fail_count']} fail "
                f"({summary['observable_trial_count']} observable)"
            )
            print(
                f"  success_rate={_format_rate(summary['observed_success_rate'])} "
                f"wilson95={interval_text}"
            )
            print(
                f"  not_observable={summary['not_observable_count']} "
                f"not_triggered={summary['not_triggered_count']}"
            )
            if summary["mean_session_success_rate"] is not None:
                print(
                    "  mean_session_rate="
                    f"{_format_rate(summary['mean_session_success_rate'])} "
                    f"scorable_sessions={summary['scorable_session_count']}"
                )
            strategies = summary["observed_strategy_ids"]
            print(
                "  strategies="
                + (", ".join(strategies) if strategies else "(not recorded)")
            )

        if report["required_failures"]:
            print("\nRequired Failures: " + ", ".join(report["required_failures"]))
        if report["required_inconclusive"]:
            print(
                "Required Inconclusive: "
                + ", ".join(report["required_inconclusive"])
            )
        if report["nonblocking_failures"]:
            print(
                "Nonblocking Failures: "
                + ", ".join(report["nonblocking_failures"])
            )
        print("Universal Success Threshold: NO")
        print("Motion Similarity Used: NO")
        print("Safety Certification: NO")

    if report["status"] == "estimated":
        return 0
    if report["status"] == "inconclusive":
        return 7
    return 8
