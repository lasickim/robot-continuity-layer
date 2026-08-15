import json
from pathlib import Path

import pytest

from rcl.experience import compact_experience
from rcl.habit_evidence import evaluate_habit_evidence_from_summary
from rcl.habit_evidence_promotion import evaluate_habit_promotion_with_formation_evidence
from rcl.habit_policy import evaluate_habit_promotion_candidates
from rcl.profile import RCLProfile, RCLValidationError


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "examples" / "history" / "mobile-base-before"
SESSION_REPORT = ROOT / "examples" / "policy" / "demo-follow-person.session-report.json"
STORE = ROOT / "examples" / "experience" / "habit-follow-person.episodes.json"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _profile():
    return RCLProfile.open(PROFILE_DIR)


def _aggregate(context=None):
    store = _load(STORE)
    summary = compact_experience(store, created_at="2026-02-01T00:00:00Z")
    return evaluate_habit_evidence_from_summary(
        summary,
        "navigation.follow_person",
        context_match=context or {},
        source_store=store,
        created_at="2026-02-01T00:00:00Z",
    )


def test_existing_promotion_semantics_remain_candidate_without_new_evidence():
    report = evaluate_habit_promotion_candidates(
        _profile(),
        _load(SESSION_REPORT),
        as_of="2026-08-14T05:20:00Z",
        created_at="2026-08-14T05:20:00Z",
    )
    decision = report["decisions"][0]
    assert decision["behavior_id"] == "navigation.follow_person"
    assert decision["decision"] == "candidate"
    assert all(item["gate"] != "habit_formation_evidence" for item in decision["gates"])


def test_sufficient_aggregate_evidence_adds_passing_gate_without_changing_candidate():
    evidence = _aggregate()
    assert evidence["evidence_basis"] == "aggregate"
    assert evidence["source_verification"] == "raw_verified"
    assert evidence["status"] == "sufficient"

    report = evaluate_habit_promotion_with_formation_evidence(
        _profile(),
        _load(SESSION_REPORT),
        formation_evidence_reports=[evidence],
        as_of="2026-08-14T05:20:00Z",
        created_at="2026-08-14T05:20:00Z",
    )
    decision = report["decisions"][0]
    gate = next(item for item in decision["gates"] if item["gate"] == "habit_formation_evidence")
    assert gate["passed"] is True
    assert gate["actual"]["evidence_basis"] == "aggregate"
    assert gate["actual"]["pseudo_episodes_created"] is False
    assert decision["decision"] == "candidate"
    assert report["eligible_count"] == 1
    assert report["blocked_count"] == 0


def test_insufficient_aggregate_evidence_blocks_review_without_creating_history():
    evidence = _aggregate({"zone": "home"})
    assert evidence["status"] == "insufficient"
    behavior_path = PROFILE_DIR / "behavior.json"
    before = behavior_path.read_bytes()

    report = evaluate_habit_promotion_with_formation_evidence(
        _profile(),
        _load(SESSION_REPORT),
        formation_evidence_reports=[evidence],
        as_of="2026-08-14T05:20:00Z",
        created_at="2026-08-14T05:20:00Z",
    )

    assert behavior_path.read_bytes() == before
    decision = report["decisions"][0]
    gate = next(item for item in decision["gates"] if item["gate"] == "habit_formation_evidence")
    assert gate["passed"] is False
    assert decision["decision"] == "blocked"
    assert report["eligible_count"] == 0
    assert report["blocked_count"] == 1
    behavior = _load(behavior_path)["behaviors"][0]
    assert len(behavior["habit"]["events"]) == 2


def test_duplicate_formation_evidence_for_one_behavior_is_rejected():
    evidence = _aggregate()
    with pytest.raises(RCLValidationError, match="Duplicate Habit Evidence Report"):
        evaluate_habit_promotion_with_formation_evidence(
            _profile(),
            _load(SESSION_REPORT),
            formation_evidence_reports=[evidence, evidence],
            as_of="2026-08-14T05:20:00Z",
        )
