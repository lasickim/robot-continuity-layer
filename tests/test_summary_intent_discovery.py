import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rcl.cli_router import main as rcl_main
from rcl.experience import compact_experience
from rcl.intent_discovery import discover_intent_candidate, discover_intent_candidate_from_summary
from rcl.profile import RCLValidationError, validate_schema


def _root():
    return Path(__file__).resolve().parents[1]


def _dataset(name):
    return json.loads((_root() / "examples" / "intent-discovery" / name).read_text())


def _hypothesis(dataset):
    return {
        "summary_hypothesis_version": "0.1",
        "dataset_id": dataset["dataset_id"],
        "candidate_action_id": dataset["candidate_action_id"],
        "context_match": copy.deepcopy(dataset["context_match"]),
        "outcome": copy.deepcopy(dataset["outcome"]),
        "proposed_intent": copy.deepcopy(dataset["proposed_intent"]),
    }


def _summary(dataset):
    start = datetime(2026, 8, 14, tzinfo=timezone.utc)
    episodes = []
    for index, episode in enumerate(dataset["episodes"]):
        episodes.append({
            "episode_id": episode["episode_id"],
            "observed_at": (start + timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
            "context": copy.deepcopy(episode["context"]),
            "action": copy.deepcopy(episode["action"]),
            "outcomes": copy.deepcopy(episode["outcomes"]),
        })
    return compact_experience({
        "experience_version": "0.1",
        "store_id": f"store-{dataset['dataset_id']}",
        "episodes": episodes,
    }, created_at="2026-08-14T08:00:00Z")


def _gates(report):
    return [(x["gate"], x["passed"], x["actual"], x["required"]) for x in report["gates"]]


def test_raw_report_declares_raw_basis():
    report = discover_intent_candidate(_dataset("object-release-stability.dataset.json"))
    assert report["evidence_basis"] == "raw"
    assert report["evidence_provenance"]["basis"] == "raw"
    assert len(report["evidence_provenance"]["dataset_digest_sha256"]) == 64
    validate_schema(report, "intent-candidate-report")


@pytest.mark.parametrize("name", ["object-release-stability.dataset.json", "dock-alignment.dataset.json"])
def test_raw_and_summary_decisions_are_equivalent(name):
    dataset = _dataset(name)
    raw = discover_intent_candidate(dataset, created_at="2026-08-14T08:10:00Z")
    summary = _summary(dataset)
    aggregate = discover_intent_candidate_from_summary(
        summary, _hypothesis(dataset), created_at="2026-08-14T08:10:00Z"
    )
    assert aggregate["evidence_basis"] == "aggregate"
    assert aggregate["candidate_id"] == raw["candidate_id"]
    assert aggregate["status"] == raw["status"]
    assert aggregate["confidence"] == raw["confidence"]
    assert aggregate["evidence"] == raw["evidence"]
    assert _gates(aggregate) == _gates(raw)
    assert aggregate["evidence_provenance"]["summary_id"] == summary["summary_id"]
    assert aggregate["causal_claim"] is False


def test_compaction_adds_action_strata_without_removing_combined_stats():
    summary = _summary(_dataset("object-release-stability.dataset.json"))
    group = next(x for x in summary["groups"] if x["context"].get("task") == "object_release")
    assert group["outcomes"]["object_stability_score"]["count"] == 20
    assert group["action_strata"]["present"]["episode_count"] == 10
    assert group["action_strata"]["absent"]["episode_count"] == 10
    validate_schema(summary, "experience-summary")


def test_legacy_summary_without_strata_is_rejected_not_reconstructed():
    dataset = _dataset("object-release-stability.dataset.json")
    summary = _summary(dataset)
    for group in summary["groups"]:
        group.pop("action_strata", None)
    validate_schema(summary, "experience-summary")
    with pytest.raises(RCLValidationError, match="action-stratified"):
        discover_intent_candidate_from_summary(summary, _hypothesis(dataset))


def test_summary_type_and_context_mismatches_are_rejected():
    dataset = _dataset("object-release-stability.dataset.json")
    hypothesis = _hypothesis(dataset)
    hypothesis["outcome"]["type"] = "binary"
    with pytest.raises(RCLValidationError, match="does not match hypothesis type"):
        discover_intent_candidate_from_summary(_summary(dataset), hypothesis)

    hypothesis = _hypothesis(dataset)
    hypothesis["context_match"] = {"task": "missing"}
    with pytest.raises(RCLValidationError, match="no groups matching"):
        discover_intent_candidate_from_summary(_summary(dataset), hypothesis)


def test_summary_discovery_public_schema_parity():
    for name in (
        "experience-summary.schema.json",
        "intent-candidate-report.schema.json",
        "intent-summary-hypothesis.schema.json",
    ):
        runtime = json.loads((_root() / "rcl" / "schemas" / name).read_text())
        public = json.loads((_root() / "spec" / "schemas" / name).read_text())
        assert runtime == public


def test_summary_cli_json(monkeypatch, capsys, tmp_path):
    dataset = _dataset("object-release-stability.dataset.json")
    summary_path = tmp_path / "summary.json"
    hypothesis_path = tmp_path / "hypothesis.json"
    summary_path.write_text(json.dumps(_summary(dataset)))
    hypothesis_path.write_text(json.dumps(_hypothesis(dataset)))
    monkeypatch.setattr(sys, "argv", [
        "rcl", "discover-intent-summary", str(summary_path), str(hypothesis_path), "--json"
    ])
    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "candidate"
    assert payload["evidence_basis"] == "aggregate"
