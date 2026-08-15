import copy
import json
from pathlib import Path

import pytest

from rcl.experience import compact_experience
from rcl.habit_evidence import (
    HABIT_EVIDENCE_METHOD,
    HABIT_EVIDENCE_VERSION,
    evaluate_habit_evidence_from_store,
    evaluate_habit_evidence_from_summary,
    load_default_habit_evidence_policy,
)
from rcl.profile import RCLValidationError, validate_schema


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "experience" / "habit-follow-person.episodes.json"


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _summary(store):
    return compact_experience(store, created_at="2026-02-01T00:00:00Z")


def _comparable(report):
    return {
        "behavior_id": report["behavior_id"],
        "action_id": report["action_id"],
        "context_match": report["context_match"],
        "metrics": report["metrics"],
        "groups": report["groups"],
        "gates": report["gates"],
        "status": report["status"],
        "supports_habit_review": report["supports_habit_review"],
    }


def test_default_policy_is_schema_valid():
    policy = load_default_habit_evidence_policy()
    validate_schema(policy, "habit-evidence-policy")
    assert policy["min_episode_count"] == 8
    assert policy["min_repeat_rate"] == 0.6


def test_raw_habit_evidence_is_sufficient_and_non_mutating():
    store = _load()
    before = copy.deepcopy(store)
    report = evaluate_habit_evidence_from_store(
        store,
        "navigation.follow_person",
        created_at="2026-02-01T00:00:00Z",
    )

    validate_schema(report, "habit-evidence-report")
    assert store == before
    assert report["habit_evidence_version"] == HABIT_EVIDENCE_VERSION == "0.1"
    assert report["method"] == HABIT_EVIDENCE_METHOD
    assert report["evidence_basis"] == "raw"
    assert report["source_verification"] == "direct_source"
    assert report["metrics"]["matched_group_count"] == 2
    assert report["metrics"]["episode_count"] == 10
    assert report["metrics"]["action_present_count"] == 8
    assert report["metrics"]["action_absent_count"] == 2
    assert report["metrics"]["repeat_rate"] == 0.8
    assert report["metrics"]["observation_span_days"] == 30.0
    assert report["status"] == "sufficient"
    assert report["supports_habit_review"] is True
    assert report["pseudo_episodes_created"] is False
    assert report["non_mutating"] is True
    assert report["formation_claim"] is False


def test_raw_and_aggregate_metrics_match_for_equivalent_evidence():
    store = _load()
    summary = _summary(store)
    raw = evaluate_habit_evidence_from_store(
        store,
        "navigation.follow_person",
        created_at="2026-02-01T00:00:00Z",
    )
    aggregate = evaluate_habit_evidence_from_summary(
        summary,
        "navigation.follow_person",
        created_at="2026-02-01T00:00:00Z",
    )

    assert _comparable(raw) == _comparable(aggregate)
    assert aggregate["evidence_basis"] == "aggregate"
    assert aggregate["source_verification"] == "summary_declared"
    assert aggregate["source"]["matched_episode_id_digest_sha256"] is None
    assert aggregate["pseudo_episodes_created"] is False


def test_aggregate_can_be_raw_verified_when_source_is_available():
    store = _load()
    summary = _summary(store)
    report = evaluate_habit_evidence_from_summary(
        summary,
        "navigation.follow_person",
        source_store=store,
        created_at="2026-02-01T00:00:00Z",
    )
    assert report["source_verification"] == "raw_verified"
    assert report["status"] == "sufficient"


def test_context_selector_can_make_evidence_insufficient():
    store = _load()
    report = evaluate_habit_evidence_from_store(
        store,
        "navigation.follow_person",
        context_match={"zone": "home"},
        created_at="2026-02-01T00:00:00Z",
    )
    assert report["metrics"]["matched_group_count"] == 1
    assert report["metrics"]["episode_count"] == 5
    assert report["metrics"]["action_present_count"] == 4
    assert report["metrics"]["repeat_rate"] == 0.8
    assert report["status"] == "insufficient"
    failed = {item["gate"] for item in report["gates"] if not item["passed"]}
    assert "episode_count" in failed
    assert "action_present_count" in failed


def test_missing_action_is_explicitly_insufficient_not_invented():
    report = evaluate_habit_evidence_from_store(
        _load(),
        "navigation.nonexistent",
        created_at="2026-02-01T00:00:00Z",
    )
    assert report["metrics"]["episode_count"] == 0
    assert report["metrics"]["repeat_rate"] is None
    assert report["groups"] == []
    assert report["status"] == "insufficient"
    assert report["pseudo_episodes_created"] is False


def test_tampered_summary_is_rejected_when_raw_verification_requested():
    store = _load()
    summary = _summary(store)
    summary["groups"][0]["action_present_count"] -= 1
    material = {
        "store_id": summary["source"]["store_id"],
        "source_digest_sha256": summary["source"]["source_digest_sha256"],
        "groups": summary["groups"],
    }
    import hashlib
    payload = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    summary["summary_id"] = "experience-summary-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    with pytest.raises(RCLValidationError, match="action_present_count"):
        evaluate_habit_evidence_from_summary(
            summary,
            "navigation.follow_person",
            source_store=store,
            created_at="2026-02-01T00:00:00Z",
        )


def test_self_binding_rejects_casually_modified_summary_without_raw_source():
    summary = _summary(_load())
    summary["groups"][0]["action_present_count"] -= 1
    with pytest.raises(RCLValidationError, match="summary_id"):
        evaluate_habit_evidence_from_summary(
            summary,
            "navigation.follow_person",
            created_at="2026-02-01T00:00:00Z",
        )


def test_runtime_and_public_habit_evidence_schemas_match():
    for name in ("habit-evidence-policy", "habit-evidence-report"):
        runtime = json.loads((ROOT / "rcl" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert runtime == public


def test_runtime_and_public_default_policy_match():
    runtime = json.loads((ROOT / "rcl" / "data" / "habit-evidence-policy-v0.1.json").read_text(encoding="utf-8"))
    public = json.loads((ROOT / "spec" / "policies" / "habit-evidence-policy-v0.1.json").read_text(encoding="utf-8"))
    assert runtime == public
