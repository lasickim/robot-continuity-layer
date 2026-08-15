import copy
import json
from pathlib import Path

import pytest

from rcl.goal_governance import (
    expected_goal_proposal_id,
    goal_proposal_sha256,
    record_goal_proposal_decision,
    review_goal_proposal,
)
from rcl.intent import validate_behavior_intent_metadata
from rcl.profile import RCLValidationError, validate_schema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "goal-governance"
POSITIVE = EXAMPLES / "recipient-ready.proposal.json"
DUPLICATE = EXAMPLES / "duplicate-sitting-goal.proposal.json"
HARDWARE = EXAMPLES / "hardware-specific-recipient.proposal.json"
OVERLAP = EXAMPLES / "overlap-sitting-goal.proposal.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_portable_proposal_is_ready_for_review():
    proposal = _load(POSITIVE)
    assert expected_goal_proposal_id(proposal) == proposal["proposal_id"]
    report = review_goal_proposal(proposal)

    validate_schema(report, "goal-vocabulary-review-report")
    assert report["status"] == "ready_for_review"
    assert report["eligible_for_approval"] is True
    assert report["recommended_decision"] == "approved"
    assert report["blockers"] == []
    assert report["advisories"] == []
    assert report["vocabulary_mutated"] is False


def test_exact_registered_goal_collision_is_blocked():
    report = review_goal_proposal(_load(DUPLICATE))
    assert report["status"] == "blocked"
    assert report["eligible_for_approval"] is False
    assert "exact_goal_id_collision" in report["blockers"]


def test_hardware_specific_wording_requests_revision_but_is_not_hard_blocked():
    report = review_goal_proposal(_load(HARDWARE))
    assert report["status"] == "needs_revision"
    assert report["eligible_for_approval"] is True
    assert "body_neutrality" in report["advisories"]
    terms = {item["term"] for item in report["specificity_hits"]}
    assert {"camera", "servo"} <= terms


def test_semantic_overlap_is_advisory_not_exact_collision():
    report = review_goal_proposal(_load(OVERLAP))
    assert report["status"] == "needs_revision"
    assert report["eligible_for_approval"] is True
    assert report["blockers"] == []
    assert "semantic_overlap" in report["advisories"]
    assert report["overlap_candidates"][0]["goal_id"] == "safety.verify_sitting_area_clear"
    assert report["overlap_candidates"][0]["token_overlap"] >= 0.35


def test_proposal_id_is_bound_to_exact_proposal_material():
    proposal = _load(POSITIVE)
    proposal["portability_rationale"] += " Revised wording."
    report = review_goal_proposal(proposal)
    assert report["status"] == "blocked"
    assert "proposal_id_integrity" in report["blockers"]
    assert expected_goal_proposal_id(proposal) != proposal["proposal_id"]


def test_explicit_approval_record_is_bound_to_exact_proposal_and_does_not_mutate_vocabulary():
    proposal = _load(POSITIVE)
    review = review_goal_proposal(proposal, created_at="2026-08-15T15:00:00Z")
    record = record_goal_proposal_decision(
        proposal,
        review,
        decision="approved",
        reviewed_at="2026-08-15T15:10:00Z",
        reviewed_by="reviewer@example.org",
        reason="Portable semantic purpose with no unresolved blockers.",
    )

    validate_schema(record, "goal-vocabulary-decision-record")
    assert record["decision"] == "approved"
    assert record["proposal_sha256"] == goal_proposal_sha256(proposal)
    assert record["vocabulary_mutated"] is False
    assert record["next_action"] == "submit_explicit_vocabulary_change"


def test_advisory_proposal_can_be_explicitly_approved_with_human_reason():
    proposal = _load(OVERLAP)
    review = review_goal_proposal(proposal, created_at="2026-08-15T15:00:00Z")
    assert review["status"] == "needs_revision"
    assert review["eligible_for_approval"] is True

    record = record_goal_proposal_decision(
        proposal,
        review,
        decision="approved",
        reviewed_at="2026-08-15T15:10:00Z",
        reviewed_by="reviewer@example.org",
        reason="Reviewer accepts the semantic distinction despite overlap warning.",
    )
    assert record["decision"] == "approved"


def test_blocked_proposal_cannot_be_approved():
    proposal = _load(DUPLICATE)
    review = review_goal_proposal(proposal)
    with pytest.raises(RCLValidationError, match="cannot be approved"):
        record_goal_proposal_decision(
            proposal,
            review,
            decision="approved",
            reviewed_at="2026-08-15T15:10:00Z",
            reviewed_by="reviewer@example.org",
            reason="Should not be accepted.",
        )


def test_modified_proposal_rejects_stale_review_binding():
    proposal = _load(POSITIVE)
    review = review_goal_proposal(proposal)
    changed = copy.deepcopy(proposal)
    changed["evidence_refs"].append("proposal://demo/new-evidence")
    changed["proposal_id"] = expected_goal_proposal_id(changed)

    with pytest.raises(RCLValidationError, match="proposal_id does not match|stale"):
        record_goal_proposal_decision(
            changed,
            review,
            decision="needs_revision",
            reviewed_at="2026-08-15T15:10:00Z",
            reviewed_by="reviewer@example.org",
            reason="Proposal changed after review.",
        )


def test_experimental_extension_goals_remain_usable_without_standard_governance():
    behavior = {
        "behaviors": [
            {
                "behavior_id": "interaction.experimental_ready_check",
                "parameters": {},
                "preservation": {"priority": "optional", "mode": "semantic"},
                "intent": {
                    "goal_id": "x.acme.verify_recipient_ready",
                    "trigger": "interaction.before_transfer_commit",
                    "success_condition": "state.recipient_ready",
                    "failure_action": "retry",
                    "criticality": "preferred",
                    "required_capabilities": ["x.acme.recipient_readiness"],
                },
            }
        ]
    }
    validate_behavior_intent_metadata(behavior)


def test_runtime_and_public_goal_governance_schemas_match():
    for name in (
        "goal-vocabulary-proposal.schema.json",
        "goal-vocabulary-review-report.schema.json",
        "goal-vocabulary-decision-record.schema.json",
    ):
        runtime = json.loads((ROOT / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == public
