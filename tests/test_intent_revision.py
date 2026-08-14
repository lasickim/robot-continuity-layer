import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from rcl.cli_router import main as routed_main
from rcl.intent_revision import apply_intent_revision, preview_intent_revision
from rcl.profile import PAYLOADS, RCLProfile, RCLValidationError, validate_schema
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    profile = RCLProfile(_root() / "examples" / "intent" / "sit-assistant-v1")
    profile.validate(require_manifest=False)
    return profile


def _behavior(profile: RCLProfile, behavior_id: str = "safety.pre_sit_clearance_check") -> dict:
    return next(
        item for item in profile.load("behavior.json")["behaviors"]
        if item["behavior_id"] == behavior_id
    )


def _sha(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _candidate(profile: RCLProfile, *, candidate_id: str = "seat-revision-001", created_at: str = "2026-08-15T00:00:00Z") -> dict:
    current = _behavior(profile)["intent"]
    return {
        "revision_candidate_version": "0.1",
        "candidate_id": candidate_id,
        "created_at": created_at,
        "behavior_id": "safety.pre_sit_clearance_check",
        "current_intent_sha256": _sha(current),
        "replacement_intent": {
            "goal_id": "x.rcl-demo.verify_sitting_support_ready",
            "description": "Verify that the intended support surface is both clear and structurally ready before sitting.",
            "trigger": "activity.before_sit_down",
            "success_condition": "state.sitting_support_ready",
            "failure_action": "block",
            "criticality": "required",
            "required_capabilities": ["x.rcl-demo.sitting_support_observation"],
            "constraints": ["safety.no_unverified_sit"]
        },
        "reason": "Later observations indicate the behavior checks support readiness, not only object clearance.",
        "evidence_refs": ["experience-summary://seat-support-2026-08"],
        "proposed_by": "review-system",
        "causal_claim": False,
    }


def test_preview_is_deterministic_and_non_mutating():
    profile = _profile()
    before = copy.deepcopy(profile.load("behavior.json"))
    candidate = _candidate(profile)

    first = preview_intent_revision(
        profile, candidate, "safety.pre_sit_clearance_check",
        approved_at="2026-08-15T01:00:00Z", approved_by="demo-user",
    )
    second = preview_intent_revision(
        profile, candidate, "safety.pre_sit_clearance_check",
        approved_at="2026-08-15T01:00:00Z", approved_by="demo-user",
    )

    validate_schema(first, "intent-revision-patch")
    assert first == second
    assert first["before_intent"] == _behavior(profile)["intent"]
    assert first["history_entry"]["intent_snapshot"] == first["before_intent"]
    assert first["after_intent"]["provenance"]["source"] == "revised"
    assert first["history_entry"]["from_intent_sha256"] == _sha(first["before_intent"])
    assert first["history_entry"]["to_intent_sha256"] == _sha(first["after_intent"])
    assert profile.load("behavior.json") == before


def test_apply_preserves_previous_intent_and_other_behavior_fields(tmp_path):
    profile = _profile()
    before_behavior = copy.deepcopy(_behavior(profile))
    source_bytes = {name: (profile.root / name).read_bytes() for name in PAYLOADS}
    output = tmp_path / "revised"

    result = apply_intent_revision(
        profile, _candidate(profile), "safety.pre_sit_clearance_check", output,
        approved_at="2026-08-15T01:00:00Z", approved_by="demo-user",
    )

    validate_schema(result, "intent-revision-result")
    assert result["source_unchanged"] is True
    assert result["output_valid"] is True
    assert {name: (profile.root / name).read_bytes() for name in PAYLOADS} == source_bytes

    revised = RCLProfile.open(output)
    after = _behavior(revised)
    assert after["intent"]["goal_id"] == "x.rcl-demo.verify_sitting_support_ready"
    assert len(after["intent_history"]) == 1
    assert after["intent_history"][0]["intent_snapshot"] == before_behavior["intent"]

    before_other = copy.deepcopy(before_behavior)
    after_other = copy.deepcopy(after)
    before_other.pop("intent", None)
    after_other.pop("intent", None)
    after_other.pop("intent_history", None)
    assert after_other == before_other

    diff = diff_profiles(profile, revised)
    fields = {item["field"] for item in diff["behavior_changes"][0]["field_changes"]}
    assert "intent.goal_id" in fields
    assert "intent.provenance" in fields
    assert "intent_history" in fields
    assert diff["behavior_changes"][0]["parameter_changes"] == []


def test_two_revisions_form_append_only_digest_chain(tmp_path):
    profile = _profile()
    first_output = tmp_path / "rev1"
    apply_intent_revision(
        profile, _candidate(profile), "safety.pre_sit_clearance_check", first_output,
        approved_at="2026-08-15T01:00:00Z", approved_by="demo-user",
    )
    rev1 = RCLProfile.open(first_output)

    current = _behavior(rev1)["intent"]
    candidate2 = {
        "revision_candidate_version": "0.1",
        "candidate_id": "seat-revision-002",
        "created_at": "2026-09-01T00:00:00Z",
        "behavior_id": "safety.pre_sit_clearance_check",
        "current_intent_sha256": _sha(current),
        "replacement_intent": {
            "goal_id": "x.rcl-demo.verify_sit_execution_ready",
            "description": "Verify clearance, support readiness, and execution readiness before sitting.",
            "trigger": "activity.before_sit_down",
            "success_condition": "state.sit_execution_ready",
            "failure_action": "block",
            "criticality": "required",
            "required_capabilities": ["x.rcl-demo.sit_readiness_observation"],
            "constraints": ["safety.no_unverified_sit"]
        },
        "reason": "Longer-term evidence shows the check also covers execution readiness.",
        "evidence_refs": ["experience-summary://sit-readiness-2026-09"],
        "causal_claim": False,
    }
    second_output = tmp_path / "rev2"
    apply_intent_revision(
        rev1, candidate2, "safety.pre_sit_clearance_check", second_output,
        approved_at="2026-09-01T01:00:00Z", approved_by="demo-user",
    )

    rev2 = RCLProfile.open(second_output)
    behavior = _behavior(rev2)
    history = behavior["intent_history"]
    assert len(history) == 2
    assert history[0]["to_intent_sha256"] == history[1]["from_intent_sha256"]
    assert history[1]["intent_snapshot"] == current
    assert history[-1]["to_intent_sha256"] == _sha(behavior["intent"])


def test_stale_candidate_and_no_intent_are_rejected():
    profile = _profile()
    candidate = _candidate(profile)
    candidate["current_intent_sha256"] = "0" * 64
    with pytest.raises(RCLValidationError, match="does not match"):
        preview_intent_revision(
            profile, candidate, "safety.pre_sit_clearance_check",
            approved_at="2026-08-15T01:00:00Z",
        )

    no_intent = RCLProfile(_root() / "examples" / "intent-approval" / "object-release-before")
    no_intent.validate(require_manifest=False)
    fake = {
        "revision_candidate_version": "0.1",
        "candidate_id": "no-intent",
        "created_at": "2026-08-15T00:00:00Z",
        "behavior_id": "interaction.post_release_hold",
        "current_intent_sha256": "0" * 64,
        "replacement_intent": {
            "goal_id": "x.rcl-demo.some_goal",
            "trigger": "activity.after_object_release",
            "success_condition": "state.object_stable",
            "failure_action": "retry",
            "criticality": "preferred",
            "required_capabilities": ["x.rcl-demo.object_stability_observation"]
        },
        "reason": "test",
        "evidence_refs": ["test://evidence"],
        "causal_claim": False,
    }
    with pytest.raises(RCLValidationError, match="requires an existing declared intent"):
        preview_intent_revision(
            no_intent, fake, "interaction.post_release_hold",
            approved_at="2026-08-15T01:00:00Z",
        )


def test_noop_and_backdated_revision_are_rejected():
    profile = _profile()
    candidate = _candidate(profile)
    current = copy.deepcopy(_behavior(profile)["intent"])
    current.pop("provenance", None)
    candidate["replacement_intent"] = current
    with pytest.raises(RCLValidationError, match="semantically unchanged"):
        preview_intent_revision(
            profile, candidate, "safety.pre_sit_clearance_check",
            approved_at="2026-08-15T01:00:00Z",
        )

    candidate = _candidate(profile)
    with pytest.raises(RCLValidationError, match="cannot precede"):
        preview_intent_revision(
            profile, candidate, "safety.pre_sit_clearance_check",
            approved_at="2026-08-14T23:00:00Z",
        )


def test_history_tampering_is_rejected(tmp_path):
    profile = _profile()
    output = tmp_path / "rev1"
    apply_intent_revision(
        profile, _candidate(profile), "safety.pre_sit_clearance_check", output,
        approved_at="2026-08-15T01:00:00Z",
    )
    payload_path = output / "behavior.json"
    payload = json.loads(payload_path.read_text())
    payload["behaviors"][0]["intent_history"][0]["intent_snapshot"]["description"] = "tampered"
    payload_path.write_text(json.dumps(payload, indent=2) + "\n")
    (output / "manifest.json").unlink()

    with pytest.raises(RCLValidationError, match="from_intent_sha256"):
        RCLProfile(output).validate(require_manifest=False)


def test_cli_preview_and_apply(monkeypatch, capsys, tmp_path):
    profile = _profile()
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(_candidate(profile)), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "rcl", "revise-intent", "preview", str(profile.root), str(candidate_path),
        "safety.pre_sit_clearance_check", "--approved-at", "2026-08-15T01:00:00Z", "--json",
    ])
    assert routed_main() == 0
    patch = json.loads(capsys.readouterr().out)
    assert patch["after_intent"]["provenance"]["source"] == "revised"

    output = tmp_path / "cli-revised"
    monkeypatch.setattr(sys, "argv", [
        "rcl", "revise-intent", "apply", str(profile.root), str(candidate_path),
        "safety.pre_sit_clearance_check", str(output), "--approved-at", "2026-08-15T01:00:00Z",
        "--approved-by", "demo-user", "--json",
    ])
    assert routed_main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["output_valid"] is True
    assert len(_behavior(RCLProfile.open(output))["intent_history"]) == 1


def test_runtime_and_public_revision_schemas_match():
    root = _root()
    for name in (
        "intent-revision-candidate.schema.json",
        "intent-revision-patch.schema.json",
        "intent-revision-result.schema.json",
    ):
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text())
        public = json.loads((root / "spec" / "schemas" / name).read_text())
        assert runtime == public

    runtime_behavior = json.loads((root / "rcl" / "schemas" / "behavior.schema.json").read_text())
    public_behavior = json.loads((root / "spec" / "schemas" / "v0.4" / "behavior.schema.json").read_text())
    assert runtime_behavior == public_behavior
