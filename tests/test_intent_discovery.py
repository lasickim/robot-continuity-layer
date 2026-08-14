import copy
import json
import sys
from pathlib import Path

import pytest

from rcl.cli_router import main as rcl_main
from rcl.intent_discovery import (
    INTENT_DISCOVERY_METHOD,
    discover_intent_candidate,
    load_default_intent_discovery_policy,
)
from rcl.profile import RCLValidationError, validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dataset(name: str) -> dict:
    return json.loads(
        (_root() / "examples" / "intent-discovery" / name).read_text(encoding="utf-8")
    )


def _failed_gates(report: dict) -> set[str]:
    return {item["gate"] for item in report["gates"] if not item["passed"]}


def test_object_release_numeric_fixture_surfaces_strong_candidate():
    dataset = _dataset("object-release-stability.dataset.json")
    report = discover_intent_candidate(
        dataset,
        created_at="2026-08-14T07:20:00Z",
    )

    validate_schema(report, "intent-candidate-report")
    assert report["method"] == INTENT_DISCOVERY_METHOD
    assert report["status"] == "candidate"
    assert report["confidence"] == "strong"
    assert report["recommended_next_action"] == "review_candidate"
    assert report["causal_claim"] is False
    assert report["evidence"]["context_episode_count"] == 20
    assert report["evidence"]["ignored_episode_count"] == 2
    assert report["evidence"]["action_present_count"] == 10
    assert report["evidence"]["action_absent_count"] == 10
    assert report["evidence"]["action_repeat_rate"] == 0.5
    assert report["evidence"]["beneficial_effect"] > 0.3
    assert report["hypothesis"]["proposed_intent"]["goal_id"] == "x.rcl-demo.stabilize_released_object"


def test_unrelated_binary_docking_fixture_uses_same_engine():
    report = discover_intent_candidate(_dataset("dock-alignment.dataset.json"))

    assert report["status"] == "candidate"
    assert report["confidence"] == "moderate"
    assert report["evidence"]["outcome_type"] == "binary"
    assert report["evidence"]["action_present_mean"] == pytest.approx(5 / 6, abs=1e-6)
    assert report["evidence"]["action_absent_mean"] == pytest.approx(2 / 6, abs=1e-6)
    assert report["evidence"]["beneficial_effect"] == pytest.approx(0.5, abs=1e-6)
    assert report["hypothesis"]["candidate_action_id"] == "navigation.pre_dock_alignment_pause"


def test_lower_is_better_numeric_outcome_is_supported():
    dataset = _dataset("object-release-stability.dataset.json")
    dataset["dataset_id"] = "demo-object-release-instability-001"
    dataset["outcome"] = {
        "outcome_id": "object_instability_score",
        "type": "numeric",
        "higher_is_better": False,
        "minimum_meaningful_effect": 0.15,
        "unit": "ratio",
    }
    for episode in dataset["episodes"]:
        stability = episode["outcomes"].pop("object_stability_score")
        episode["outcomes"]["object_instability_score"] = 1.0 - stability

    report = discover_intent_candidate(dataset)

    assert report["status"] == "candidate"
    assert report["evidence"]["raw_difference"] < 0
    assert report["evidence"]["beneficial_effect"] > 0.3
    assert report["evidence"]["effect_direction"] == "beneficial"


def test_insufficient_samples_are_reported_not_promoted():
    dataset = _dataset("object-release-stability.dataset.json")
    dataset["episodes"] = dataset["episodes"][:6]

    report = discover_intent_candidate(dataset)

    assert report["status"] == "insufficient_evidence"
    assert report["confidence"] == "insufficient"
    assert report["recommended_next_action"] == "collect_more_evidence"
    failed = _failed_gates(report)
    assert "context_episodes" in failed
    assert "action_absent_samples" in failed
    assert "meaningful_outcome_association" in failed


def test_weak_repetition_is_not_called_an_intent_candidate():
    dataset = _dataset("dock-alignment.dataset.json")
    for index, episode in enumerate(dataset["episodes"]):
        episode["action"]["performed"] = index < 2
        episode["outcomes"]["dock_success"] = bool(index < 2)

    report = discover_intent_candidate(dataset)

    assert report["status"] == "insufficient_evidence"
    failed = _failed_gates(report)
    assert "action_present_samples" in failed
    assert "action_repeat_rate" in failed


def test_weak_outcome_association_is_not_promoted():
    dataset = _dataset("object-release-stability.dataset.json")
    for episode in dataset["episodes"]:
        if episode["context"].get("task") == "object_release" and not episode["action"]["performed"]:
            episode["outcomes"]["object_stability_score"] = 0.90

    report = discover_intent_candidate(dataset)

    assert report["status"] == "insufficient_evidence"
    assert report["evidence"]["effect_direction"] == "neutral_or_harmful"
    assert "meaningful_outcome_association" in _failed_gates(report)


def test_custom_policy_can_change_sample_gate_without_changing_effect_gate():
    dataset = _dataset("dock-alignment.dataset.json")
    policy = load_default_intent_discovery_policy()
    policy["min_context_episodes"] = 12
    policy["min_action_present"] = 6
    policy["min_action_absent"] = 6
    policy["min_action_repeat_rate"] = 0.5

    report = discover_intent_candidate(dataset, policy=policy)

    assert report["status"] == "candidate"
    assert report["policy"]["policy_id"] == "rcl.intent.discovery.default.v0.1"


def test_discovery_is_deterministic_and_does_not_mutate_input():
    dataset = _dataset("object-release-stability.dataset.json")
    before = copy.deepcopy(dataset)

    first = discover_intent_candidate(dataset, created_at="2026-08-14T07:20:00Z")
    second = discover_intent_candidate(dataset, created_at="2026-08-14T07:20:00Z")

    assert dataset == before
    assert first == second
    assert first["candidate_id"] == second["candidate_id"]


def test_mismatched_episode_action_id_is_rejected():
    dataset = _dataset("dock-alignment.dataset.json")
    dataset["episodes"][0]["action"]["action_id"] = "navigation.some_other_action"

    with pytest.raises(RCLValidationError, match="does not match candidate_action_id"):
        discover_intent_candidate(dataset)


def test_registered_goal_still_obeys_intent_vocabulary_rules():
    dataset = _dataset("object-release-stability.dataset.json")
    dataset["proposed_intent"] = {
        "goal_id": "safety.verify_sitting_area_clear",
        "description": "Deliberately invalid trigger for a registered goal.",
        "trigger": "activity.after_object_release",
        "success_condition": "state.sitting_area_clear",
        "failure_action": "block",
        "criticality": "required",
        "required_capabilities": ["perception.sitting_area_clearance"],
    }

    with pytest.raises(RCLValidationError, match="is not registered"):
        discover_intent_candidate(dataset)


def test_default_policy_and_public_artifacts_match_runtime():
    root = _root()
    policy = load_default_intent_discovery_policy()
    published_policy = json.loads(
        (root / "spec" / "policies" / "intent-discovery-policy-v0.1.json").read_text(encoding="utf-8")
    )
    assert policy == published_policy
    validate_schema(policy, "intent-discovery-policy")

    for name in (
        "intent-discovery-dataset.schema.json",
        "intent-discovery-policy.schema.json",
        "intent-candidate-report.schema.json",
    ):
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        published = json.loads((root / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == published


def test_reference_datasets_validate():
    validate_schema(_dataset("object-release-stability.dataset.json"), "intent-discovery-dataset")
    validate_schema(_dataset("dock-alignment.dataset.json"), "intent-discovery-dataset")


def test_discover_intent_cli_json(monkeypatch, capsys):
    dataset_path = _root() / "examples" / "intent-discovery" / "object-release-stability.dataset.json"
    monkeypatch.setattr(sys, "argv", ["rcl", "discover-intent", str(dataset_path), "--json"])

    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "candidate"
    assert payload["causal_claim"] is False
    assert payload["hypothesis"]["candidate_action_id"] == "interaction.post_release_hold"
