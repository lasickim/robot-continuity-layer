import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rcl.experience import compact_experience
from rcl.intent_discovery import discover_intent_candidate, discover_intent_candidate_from_summary
from rcl.profile import RCLValidationError


def _root():
    return Path(__file__).resolve().parents[1]


def _dataset():
    return json.loads((_root() / "examples" / "intent-discovery" / "object-release-stability.dataset.json").read_text())


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
    for i, episode in enumerate(dataset["episodes"]):
        episodes.append({
            "episode_id": episode["episode_id"],
            "observed_at": (start + timedelta(seconds=i)).isoformat().replace("+00:00", "Z"),
            "context": copy.deepcopy(episode["context"]),
            "action": copy.deepcopy(episode["action"]),
            "outcomes": copy.deepcopy(episode["outcomes"]),
        })
    return compact_experience({"experience_version": "0.1", "store_id": "edge-store", "episodes": episodes})


def test_lower_is_better_matches_raw_after_compaction():
    dataset = _dataset()
    dataset["dataset_id"] = "aggregate-lower-is-better"
    dataset["outcome"] = {
        "outcome_id": "object_instability_score",
        "type": "numeric",
        "higher_is_better": False,
        "minimum_meaningful_effect": 0.15,
        "unit": "ratio",
    }
    for episode in dataset["episodes"]:
        value = episode["outcomes"].pop("object_stability_score")
        episode["outcomes"]["object_instability_score"] = 1.0 - value
    raw = discover_intent_candidate(dataset)
    aggregate = discover_intent_candidate_from_summary(_summary(dataset), _hypothesis(dataset))
    assert aggregate["evidence"] == raw["evidence"]
    assert aggregate["status"] == "candidate"
    assert aggregate["evidence"]["raw_difference"] < 0


def test_malformed_summary_action_counts_are_rejected():
    dataset = _dataset()
    summary = _summary(dataset)
    summary["groups"][0]["action_present_count"] += 1
    with pytest.raises(RCLValidationError, match="do not sum"):
        discover_intent_candidate_from_summary(summary, _hypothesis(dataset))


def test_summary_discovery_is_deterministic_and_non_mutating():
    dataset = _dataset()
    summary = _summary(dataset)
    hypothesis = _hypothesis(dataset)
    before_summary = copy.deepcopy(summary)
    before_hypothesis = copy.deepcopy(hypothesis)
    first = discover_intent_candidate_from_summary(summary, hypothesis, created_at="2026-08-14T09:00:00Z")
    second = discover_intent_candidate_from_summary(summary, hypothesis, created_at="2026-08-14T09:00:00Z")
    assert first == second
    assert summary == before_summary
    assert hypothesis == before_hypothesis
