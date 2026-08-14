import copy
import json
import sys
from pathlib import Path

from rcl.cli import main as rcl_main
from rcl.habit_policy import (
    evaluate_habit_promotion_candidates,
    load_default_habit_promotion_policy,
)
from rcl.profile import RCLProfile, validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile(name: str) -> RCLProfile:
    profile = RCLProfile(_root() / "examples" / "history" / name)
    profile.validate(require_manifest=False)
    return profile


def _session_report() -> dict:
    return json.loads(
        (_root() / "examples" / "policy" / "demo-follow-person.session-report.json").read_text()
    )


def _decision(report: dict, behavior_id: str) -> dict:
    return next(item for item in report["decisions"] if item["behavior_id"] == behavior_id)


def _failed_gates(decision: dict) -> set[str]:
    return {item["gate"] for item in decision["gates"] if not item["passed"]}


def test_default_policy_detects_learning_to_stable_candidate_without_mutation():
    profile = _profile("mobile-base-before")
    before_payload = copy.deepcopy(profile.load("behavior.json"))

    report = evaluate_habit_promotion_candidates(
        profile,
        _session_report(),
        created_at="2026-08-14T05:21:00Z",
    )

    validate_schema(report, "habit-promotion-report")
    decision = _decision(report, "navigation.follow_person")
    assert decision["current_lifecycle"] == "learning"
    assert decision["recommended_lifecycle"] == "stable"
    assert decision["decision"] == "candidate"
    assert decision["eligible"] is True
    assert decision["qualifying_metric_count"] == 2
    assert report["eligible_count"] == 1
    assert profile.load("behavior.json") == before_payload


def test_insufficient_session_evidence_blocks_stable_candidate():
    evidence = _session_report()
    evidence["scorable_session_count"] = 2
    evidence["successful_session_count"] = 2
    evidence["failed_session_count"] = 1
    evidence["failed_session_ids"] = ["day-3"]
    evidence["evaluation_success"] = False
    evidence["status"] = "insufficient_sessions"
    evidence["confidence_interval_95"] = None
    for metric in evidence["metric_summaries"]:
        metric["session_count"] = 2
        metric["confidence_interval_95"] = None

    report = evaluate_habit_promotion_candidates(_profile("mobile-base-before"), evidence)
    decision = _decision(report, "navigation.follow_person")

    assert decision["eligible"] is False
    assert decision["decision"] == "blocked"
    failed = _failed_gates(decision)
    assert "session_evaluation_success" in failed
    assert "session_report_status" in failed
    assert "scorable_sessions" in failed
    assert "score_ci_half_width" in failed
    assert "qualifying_behavior_metrics" in failed


def test_wide_score_confidence_interval_blocks_promotion():
    evidence = _session_report()
    evidence["confidence_interval_95"] = {
        "low": 88.0,
        "high": 100.0,
        "half_width": 10.0,
        "critical_value": 4.303,
    }

    report = evaluate_habit_promotion_candidates(_profile("mobile-base-before"), evidence)
    decision = _decision(report, "navigation.follow_person")

    assert decision["eligible"] is False
    assert "score_ci_half_width" in _failed_gates(decision)


def test_session_failure_is_never_averaged_into_candidate():
    evidence = _session_report()
    evidence["evaluation_success"] = False
    evidence["status"] = "session_failures"
    evidence["failed_session_count"] = 1
    evidence["failed_session_ids"] = ["day-2"]

    report = evaluate_habit_promotion_candidates(_profile("mobile-base-before"), evidence)
    decision = _decision(report, "navigation.follow_person")

    assert decision["eligible"] is False
    assert "session_evaluation_success" in _failed_gates(decision)
    assert "session_report_status" in _failed_gates(decision)


def test_default_policy_keeps_recent_stable_habits_out_of_legacy():
    report = evaluate_habit_promotion_candidates(
        _profile("mobile-base-after"),
        _session_report(),
    )
    follow = _decision(report, "navigation.follow_person")

    assert follow["current_lifecycle"] == "stable"
    assert follow["recommended_lifecycle"] == "legacy"
    assert follow["eligible"] is False
    failed = _failed_gates(follow)
    assert "stable_age_days" in failed
    assert "scorable_sessions" in failed


def test_custom_review_policy_can_surface_legacy_candidate_after_long_stability():
    policy = load_default_habit_promotion_policy()
    legacy = policy["transitions"]["stable_to_legacy"]
    legacy["min_stable_days"] = 30
    legacy["evidence"]["min_scorable_sessions"] = 3

    report = evaluate_habit_promotion_candidates(
        _profile("mobile-base-after"),
        _session_report(),
        policy=policy,
        as_of="2026-08-14T05:20:00Z",
    )
    follow = _decision(report, "navigation.follow_person")
    turn = _decision(report, "navigation.pre_turn_observation")

    assert follow["eligible"] is True
    assert follow["decision"] == "candidate"
    assert follow["recommended_lifecycle"] == "legacy"
    assert turn["eligible"] is False


def test_default_policy_and_reference_evidence_validate():
    policy = load_default_habit_promotion_policy()
    validate_schema(policy, "habit-promotion-policy")
    validate_schema(_session_report(), "session-evaluation-report")


def test_habit_candidates_cli_json(monkeypatch, capsys):
    root = _root()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "habit-candidates",
            str(root / "examples" / "history" / "mobile-base-before"),
            str(root / "examples" / "policy" / "demo-follow-person.session-report.json"),
            "--json",
        ],
    )

    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["promotion_version"] == "0.1"
    assert payload["method"] == "rcl.habit.promotion.review.v0.1"
    assert payload["eligible_count"] == 1
    assert _decision(payload, "navigation.follow_person")["recommended_lifecycle"] == "stable"
