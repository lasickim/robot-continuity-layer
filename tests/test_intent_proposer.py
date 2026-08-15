import copy
import json
from pathlib import Path

import pytest

from rcl.intent_discovery import discover_intent_candidate
from rcl.intent_proposer import (
    DeterministicReferenceProposer,
    ProposerMetadata,
    build_intent_hypothesis_proposal,
    expected_intent_hypothesis_proposal_id,
    intent_hypothesis_proposal_sha256,
    proposal_to_raw_discovery_dataset,
    proposal_to_summary_hypothesis,
    run_intent_hypothesis_proposer,
    validate_intent_hypothesis_proposal,
)
from rcl.profile import RCLValidationError, validate_schema


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "intent-proposer"
DISCOVERY = ROOT / "examples" / "intent-discovery" / "object-release-stability.dataset.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _proposal(name: str):
    return _load(FIXTURES / name)


def test_human_rule_llm_and_vlm_proposals_are_schema_valid_and_bound():
    expected_kinds = {
        "human-object-release.proposal.json": "human",
        "rule-object-release.proposal.json": "rule_based",
        "llm-object-release.proposal.json": "llm",
        "vlm-object-release.proposal.json": "vlm",
    }
    for filename, kind in expected_kinds.items():
        proposal = _proposal(filename)
        validate_intent_hypothesis_proposal(proposal)
        assert proposal["proposer"]["kind"] == kind
        assert proposal["proposal_id"] == expected_intent_hypothesis_proposal_id(proposal)
        assert len(intent_hypothesis_proposal_sha256(proposal)) == 64
        assert proposal["status"] == "proposed"
        assert proposal["non_mutating"] is True
        assert proposal["approved"] is False


def test_model_self_confidence_is_explicitly_non_normative():
    proposal = _proposal("llm-object-release.proposal.json")
    assert proposal["self_confidence"] == 0.92
    assert proposal["self_confidence_semantics"] == "proposer_self_reported_non_normative"

    evidence = _load(DISCOVERY)
    dataset = proposal_to_raw_discovery_dataset(
        proposal,
        dataset_id="proposer-llm-object-release",
        episodes=evidence["episodes"],
    )
    candidate = discover_intent_candidate(dataset, created_at="2026-08-16T01:30:00+09:00")
    assert candidate["confidence"] in {"strong", "moderate", "insufficient"}
    assert candidate["confidence"] != proposal["self_confidence"]


def test_stale_or_modified_proposal_material_is_rejected():
    proposal = _proposal("human-object-release.proposal.json")
    proposal["rationale_summary"] += " Additional wording."
    with pytest.raises(RCLValidationError, match="proposal_id does not match"):
        validate_intent_hypothesis_proposal(proposal)


def test_hidden_reasoning_field_is_not_part_of_the_interchange_contract():
    proposal = _proposal("llm-object-release.proposal.json")
    proposal["chain_of_thought"] = "private hidden reasoning"
    with pytest.raises(RCLValidationError):
        validate_intent_hypothesis_proposal(proposal)


def test_raw_conversion_copies_caller_supplied_episodes_without_fabrication():
    proposal = _proposal("human-object-release.proposal.json")
    source = _load(DISCOVERY)
    episodes = copy.deepcopy(source["episodes"])
    dataset = proposal_to_raw_discovery_dataset(
        proposal,
        dataset_id="proposal-raw-conversion",
        episodes=episodes,
    )

    assert dataset["episodes"] == episodes
    assert dataset["episodes"] is not episodes
    assert dataset["candidate_action_id"] == proposal["candidate_action_id"]
    assert dataset["proposed_intent"] == proposal["proposed_intent"]
    discover_intent_candidate(dataset, created_at="2026-08-16T01:30:00+09:00")


def test_summary_conversion_contains_hypothesis_only_and_no_statistics():
    proposal = _proposal("vlm-object-release.proposal.json")
    hypothesis = proposal_to_summary_hypothesis(proposal, dataset_id="proposal-summary-conversion")

    assert set(hypothesis) == {
        "summary_hypothesis_version",
        "dataset_id",
        "candidate_action_id",
        "context_match",
        "outcome",
        "proposed_intent",
    }
    assert "episodes" not in hypothesis
    assert "groups" not in hypothesis
    assert "episode_count" not in hypothesis
    assert "self_confidence" not in hypothesis


def test_capability_path_intent_can_flow_through_both_conversion_helpers():
    source = _proposal("rule-object-release.proposal.json")
    intent = copy.deepcopy(source["proposed_intent"])
    intent.pop("required_capabilities")
    intent["capability_paths"] = [
        {
            "path_id": "direct_stability_observation",
            "all_of": ["x.rcl-demo.object_stability_observation"],
        },
        {
            "path_id": "external_stability_state",
            "any_of": [
                "x.rcl-demo.external_stability_state",
                "x.rcl-demo.object_stability_observation",
            ],
        },
    ]
    proposal = build_intent_hypothesis_proposal(
        created_at=source["created_at"],
        proposer=source["proposer"],
        candidate_action_id=source["candidate_action_id"],
        context_match=source["context_match"],
        outcome=source["outcome"],
        proposed_intent=intent,
        rationale_summary=source["rationale_summary"],
        evidence_refs=source["evidence_refs"],
    )

    hypothesis = proposal_to_summary_hypothesis(proposal, dataset_id="capability-path-summary")
    assert hypothesis["proposed_intent"]["capability_paths"] == intent["capability_paths"]

    episodes = _load(DISCOVERY)["episodes"]
    dataset = proposal_to_raw_discovery_dataset(
        proposal,
        dataset_id="capability-path-raw",
        episodes=episodes,
    )
    assert dataset["proposed_intent"]["capability_paths"] == intent["capability_paths"]
    discover_intent_candidate(dataset, created_at="2026-08-16T01:30:00+09:00")


def test_reference_proposer_exercises_plugin_boundary_without_external_inference():
    source = _proposal("rule-object-release.proposal.json")
    request = {
        "created_at": source["created_at"],
        "candidate_action_id": source["candidate_action_id"],
        "context_match": source["context_match"],
        "outcome": source["outcome"],
        "proposed_intent": source["proposed_intent"],
        "rationale_summary": source["rationale_summary"],
        "evidence_refs": source["evidence_refs"],
        "self_confidence": None,
    }
    before = copy.deepcopy(request)
    proposals = run_intent_hypothesis_proposer(DeterministicReferenceProposer(), request)

    assert request == before
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["proposer"] == {
        "kind": "rule_based",
        "proposer_id": "rcl.reference.intent-proposer",
        "provider": "rcl",
        "tool": "deterministic_reference",
        "version": "0.1",
    }
    validate_intent_hypothesis_proposal(proposal)


def test_plugin_cannot_lie_about_its_metadata():
    proposal = _proposal("llm-object-release.proposal.json")

    class LyingProposer:
        @property
        def metadata(self):
            return ProposerMetadata(proposer_id="human.reviewer", kind="human")

        def propose(self, request):
            return [copy.deepcopy(proposal)]

    with pytest.raises(RCLValidationError, match="metadata does not match"):
        run_intent_hypothesis_proposer(LyingProposer(), {})


def test_runtime_and_public_proposer_and_discovery_schemas_match():
    for name in (
        "intent-hypothesis-proposal.schema.json",
        "intent-discovery-dataset.schema.json",
        "intent-summary-hypothesis.schema.json",
    ):
        runtime = json.loads((ROOT / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == public


def test_proposal_schema_can_be_used_directly():
    proposal = _proposal("human-object-release.proposal.json")
    validate_schema(proposal, "intent-hypothesis-proposal")
