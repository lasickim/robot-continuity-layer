import copy
import json
from pathlib import Path

import pytest

from rcl.experience import compact_experience
from rcl.experience_retention import (
    create_experience_archive_record,
    evaluate_experience_retention,
    expected_experience_archive_id,
    load_default_experience_retention_policy,
    validate_experience_archive_record,
    verify_experience_summary_binding,
)
from rcl.profile import RCLValidationError, validate_schema


ROOT = Path(__file__).resolve().parents[1]
STORE_PATH = ROOT / "examples" / "experience" / "retention-demo.episodes.json"
AS_OF = "2026-04-01T12:00:00Z"
ARCHIVED_AT = "2026-03-31T12:00:00Z"


def _load_store():
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _summary(store, *, retained_exemplars=4):
    return compact_experience(
        store,
        created_at="2026-03-31T13:00:00Z",
        retained_exemplars=retained_exemplars,
    )


def _archive(store, episode_ids):
    return create_experience_archive_record(
        store,
        episode_ids,
        location_ref="archive://cold-store/retention-demo/001",
        archived_at=ARCHIVED_AT,
        archived_by="retention-test",
    )


def _by_id(report):
    return {item["episode_id"]: item for item in report["decisions"]}


def test_default_policy_is_schema_valid_and_conservative():
    policy = load_default_experience_retention_policy()
    validate_schema(policy, "experience-retention-policy")
    assert policy["min_active_retention_days"] == 30
    assert policy["protect_retained_exemplars"] is True
    assert policy["protect_external_evidence_refs"] is True
    assert policy["min_group_episode_count_for_prune"] == 8
    assert policy["max_prune_fraction_per_group"] == 0.5
    assert policy["require_archive_record_for_prune"] is True


def test_verified_summary_binding_accepts_exact_source_and_rejects_stale_source():
    store = _load_store()
    summary = _summary(store)
    membership = verify_experience_summary_binding(store, summary)
    assert sum(len(items) for items in membership.values()) == len(store["episodes"])

    changed = copy.deepcopy(store)
    changed["episodes"][0]["outcomes"]["object_stability"] = 0.5
    with pytest.raises(RCLValidationError, match="source digest"):
        verify_experience_summary_binding(changed, summary)


def test_summary_binding_rejects_tampered_group_statistics_even_with_source_digest():
    store = _load_store()
    summary = _summary(store)
    tampered = copy.deepcopy(summary)
    table = next(item for item in tampered["groups"] if item["context"]["surface"] == "table")
    table["outcomes"]["object_stability"]["mean"] = 0.123456
    # Keep the deterministic summary ID consistent with the tampered material so
    # the deeper source-evidence comparison is what catches the change.
    import hashlib

    material = {
        "store_id": tampered["source"]["store_id"],
        "source_digest_sha256": tampered["source"]["source_digest_sha256"],
        "groups": tampered["groups"],
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    tampered["summary_id"] = "experience-summary-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]

    with pytest.raises(RCLValidationError, match="outcomes does not match source evidence"):
        verify_experience_summary_binding(store, tampered)


def test_default_retention_marks_old_unarchived_evidence_for_archive_only():
    store = _load_store()
    summary = _summary(store)
    report = evaluate_experience_retention(
        store,
        summary,
        as_of=AS_OF,
        created_at="2026-04-01T12:01:00Z",
    )
    validate_schema(report, "experience-retention-report")
    decisions = _by_id(report)

    for episode_id in [f"table-{index:02d}" for index in range(4, 11)]:
        assert decisions[episode_id]["decision"] == "archive_candidate"
        assert "archive_record_required" in decisions[episode_id]["reasons"]

    assert decisions["table-01"]["decision"] == "retain"
    assert "retained_summary_exemplar" in decisions["table-01"]["reasons"]
    assert decisions["table-03"]["decision"] == "retain"
    assert "external_evidence_reference" in decisions["table-03"]["reasons"]
    assert decisions["table-11"]["decision"] == "retain"
    assert "within_active_retention_window" in decisions["table-11"]["reasons"]
    assert decisions["tray-03"]["decision"] == "retain"
    assert "sparse_semantic_group" in decisions["tray-03"]["reasons"]

    assert report["counts"] == {
        "total": 16,
        "retain": 9,
        "archive_candidate": 7,
        "prune_candidate": 0,
    }
    assert report["non_mutating"] is True
    assert report["prune_executed"] is False
    assert report["archive_executed_by_rcl"] is False


def test_archive_record_is_non_mutating_bound_to_exact_store_and_episode_set():
    store = _load_store()
    before = copy.deepcopy(store)
    record = _archive(store, ["table-04", "table-05", "table-06"])

    validate_schema(record, "experience-archive-record")
    validate_experience_archive_record(store, record)
    assert record["archive_id"] == expected_experience_archive_id(record)
    assert record["episode_ids"] == ["table-04", "table-05", "table-06"]
    assert record["archive_assertion"] == "deployment_asserted_external_copy"
    assert record["non_mutating"] is True
    assert record["archive_executed_by_rcl"] is False
    assert store == before


def test_archived_old_episodes_become_prune_candidates_but_group_cap_preserves_remainder():
    store = _load_store()
    summary = _summary(store)
    archive = _archive(store, [f"table-{index:02d}" for index in range(4, 11)])
    report = evaluate_experience_retention(
        store,
        summary,
        archive_records=[archive],
        as_of=AS_OF,
        created_at="2026-04-01T12:01:00Z",
    )
    decisions = _by_id(report)

    for episode_id in [f"table-{index:02d}" for index in range(4, 10)]:
        assert decisions[episode_id]["decision"] == "prune_candidate"
        assert decisions[episode_id]["archived"] is True
        assert "archive_record_present" in decisions[episode_id]["reasons"]

    assert decisions["table-10"]["decision"] == "retain"
    assert decisions["table-10"]["protected"] is True
    assert "prune_fraction_guard" in decisions["table-10"]["reasons"]
    assert decisions["table-10"]["group_prune_candidate_limit"] == 6
    assert report["counts"]["prune_candidate"] == 6


def test_archive_does_not_override_recent_exemplar_or_external_evidence_protection():
    store = _load_store()
    summary = _summary(store)
    archive = _archive(store, ["table-01", "table-03", "table-11", "table-12"])
    report = evaluate_experience_retention(
        store,
        summary,
        archive_records=[archive],
        as_of=AS_OF,
        created_at="2026-04-01T12:01:00Z",
    )
    decisions = _by_id(report)

    assert decisions["table-01"]["decision"] == "retain"
    assert "retained_summary_exemplar" in decisions["table-01"]["reasons"]
    assert decisions["table-03"]["decision"] == "retain"
    assert "external_evidence_reference" in decisions["table-03"]["reasons"]
    assert decisions["table-11"]["decision"] == "retain"
    assert "within_active_retention_window" in decisions["table-11"]["reasons"]
    assert decisions["table-12"]["decision"] == "retain"


def test_stale_archive_record_is_rejected_against_new_source_snapshot():
    store = _load_store()
    archive = _archive(store, ["table-04"])
    changed = copy.deepcopy(store)
    changed["episodes"][3]["outcomes"]["object_stability"] = 0.99

    with pytest.raises(RCLValidationError, match="stale: source digest"):
        validate_experience_archive_record(changed, archive)


def test_archive_record_rejects_unknown_duplicate_and_impossible_timestamp():
    store = _load_store()
    with pytest.raises(RCLValidationError, match="unknown episode IDs"):
        _archive(store, ["does-not-exist"])
    with pytest.raises(RCLValidationError, match="must be unique"):
        _archive(store, ["table-04", "table-04"])
    with pytest.raises(RCLValidationError, match="cannot precede"):
        create_experience_archive_record(
            store,
            ["table-04"],
            location_ref="archive://cold",
            archived_at="2025-12-01T00:00:00Z",
            archived_by="test",
        )


def test_policy_can_unprotect_external_refs_without_changing_default_policy():
    store = _load_store()
    summary = _summary(store)
    policy = load_default_experience_retention_policy()
    policy["protect_external_evidence_refs"] = False
    report = evaluate_experience_retention(
        store,
        summary,
        policy=policy,
        as_of=AS_OF,
        created_at="2026-04-01T12:01:00Z",
    )
    assert _by_id(report)["table-03"]["decision"] == "archive_candidate"
    assert load_default_experience_retention_policy()["protect_external_evidence_refs"] is True


def test_policy_without_archive_requirement_still_respects_prune_fraction_cap():
    store = _load_store()
    summary = _summary(store)
    policy = load_default_experience_retention_policy()
    policy["require_archive_record_for_prune"] = False
    report = evaluate_experience_retention(
        store,
        summary,
        policy=policy,
        as_of=AS_OF,
        created_at="2026-04-01T12:01:00Z",
    )
    decisions = _by_id(report)
    prune_ids = [
        item["episode_id"]
        for item in report["decisions"]
        if item["decision"] == "prune_candidate"
    ]
    assert prune_ids == ["table-04", "table-05", "table-06", "table-07", "table-08", "table-09"]
    assert decisions["table-10"]["decision"] == "retain"
    assert "prune_fraction_guard" in decisions["table-10"]["reasons"]


def test_evaluation_never_mutates_store_summary_or_archive_records():
    store = _load_store()
    summary = _summary(store)
    archive = _archive(store, ["table-04", "table-05"])
    before = (copy.deepcopy(store), copy.deepcopy(summary), copy.deepcopy(archive))

    evaluate_experience_retention(
        store,
        summary,
        archive_records=[archive],
        as_of=AS_OF,
        created_at="2026-04-01T12:01:00Z",
    )
    assert store == before[0]
    assert summary == before[1]
    assert archive == before[2]


def test_runtime_and_public_retention_schemas_match():
    for name in (
        "experience-retention-policy.schema.json",
        "experience-archive-record.schema.json",
        "experience-retention-report.schema.json",
    ):
        runtime = json.loads((ROOT / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == public
