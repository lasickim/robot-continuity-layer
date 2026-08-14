import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from rcl.cli_router import main as routed_main
from rcl.intent_approval import apply_intent_approval, preview_intent_approval
from rcl.intent_discovery import discover_intent_candidate
from rcl.profile import PAYLOADS, RCLProfile, RCLValidationError, validate_schema
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    profile = RCLProfile(_root() / "examples" / "intent-approval" / "object-release-before")
    profile.validate(require_manifest=False)
    return profile


def _dataset() -> dict:
    return json.loads(
        (_root() / "examples" / "intent-discovery" / "object-release-stability.dataset.json").read_text()
    )


def _candidate() -> dict:
    return discover_intent_candidate(
        _dataset(),
        created_at="2026-08-14T08:30:00Z",
    )


def _behavior(profile: RCLProfile, behavior_id: str = "interaction.post_release_hold") -> dict:
    return next(
        item for item in profile.load("behavior.json")["behaviors"]
        if item["behavior_id"] == behavior_id
    )


def _canonical_sha(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_preview_is_deterministic_non_mutating_and_records_candidate_digest():
    profile = _profile()
    before = copy.deepcopy(profile.load("behavior.json"))
    report = _candidate()

    first = preview_intent_approval(
        profile,
        report,
        "interaction.post_release_hold",
        approved_at="2026-08-14T09:00:00Z",
        approved_by="demo-user",
    )
    second = preview_intent_approval(
        profile,
        report,
        "interaction.post_release_hold",
        approved_at="2026-08-14T09:00:00Z",
        approved_by="demo-user",
    )

    validate_schema(first, "intent-approval-patch")
    assert first == second
    assert first["before_intent"] is None
    assert first["candidate"]["candidate_report_sha256"] == _canonical_sha(report)
    assert first["after_intent"]["goal_id"] == "x.rcl-demo.stabilize_released_object"
    provenance = first["after_intent"]["provenance"]
    assert provenance["source"] == "discovered"
    assert provenance["candidate_id"] == report["candidate_id"]
    assert provenance["approved_by"] == "demo-user"
    assert provenance["causal_claim"] is False
    assert profile.load("behavior.json") == before


def test_apply_closes_discovery_to_declared_intent_loop_without_changing_source(tmp_path):
    profile = _profile()
    report = _candidate()
    source_bytes = {name: (profile.root / name).read_bytes() for name in PAYLOADS}
    before_behavior = copy.deepcopy(_behavior(profile))
    output = tmp_path / "intent-approved"

    result = apply_intent_approval(
        profile,
        report,
        "interaction.post_release_hold",
        output,
        approved_at="2026-08-14T09:00:00Z",
        approved_by="demo-user",
    )

    validate_schema(result, "intent-approval-result")
    assert result["source_unchanged"] is True
    assert result["output_valid"] is True
    assert result["causal_claim"] is False
    assert result["candidate_report_sha256"] == _canonical_sha(report)
    assert {name: (profile.root / name).read_bytes() for name in PAYLOADS} == source_bytes

    approved = RCLProfile.open(output)
    after_behavior = _behavior(approved)
    assert after_behavior["parameters"] == before_behavior["parameters"]
    assert after_behavior.get("habit") == before_behavior.get("habit")
    assert after_behavior.get("expression") == before_behavior.get("expression")
    assert after_behavior["source"] == before_behavior["source"]
    assert after_behavior["confidence"] == before_behavior["confidence"]
    assert after_behavior["intent"]["goal_id"] == report["hypothesis"]["proposed_intent"]["goal_id"]
    assert after_behavior["intent"]["provenance"]["candidate_report_sha256"] == _canonical_sha(report)

    diff = diff_profiles(profile, approved)
    assert diff["summary"] == {
        "added_behaviors": 0,
        "removed_behaviors": 0,
        "modified_behaviors": 1,
    }
    change = diff["behavior_changes"][0]
    assert change["parameter_changes"] == []
    fields = {item["field"] for item in change["field_changes"]}
    assert "intent.goal_id" in fields
    assert "intent.provenance" in fields


def test_existing_intent_is_never_overwritten(tmp_path):
    profile = _profile()
    report = _candidate()
    output = tmp_path / "approved"
    apply_intent_approval(
        profile,
        report,
        "interaction.post_release_hold",
        output,
        approved_at="2026-08-14T09:00:00Z",
    )

    with pytest.raises(RCLValidationError, match="will not overwrite"):
        preview_intent_approval(
            RCLProfile.open(output),
            report,
            "interaction.post_release_hold",
            approved_at="2026-08-14T09:30:00Z",
        )


def test_insufficient_evidence_candidate_is_rejected():
    dataset = _dataset()
    dataset["outcome"]["minimum_meaningful_effect"] = 1.0
    report = discover_intent_candidate(dataset, created_at="2026-08-14T08:30:00Z")
    assert report["status"] == "insufficient_evidence"

    with pytest.raises(RCLValidationError, match="not an approvable candidate"):
        preview_intent_approval(
            _profile(),
            report,
            "interaction.post_release_hold",
            approved_at="2026-08-14T09:00:00Z",
        )


def test_forged_candidate_with_failed_gate_is_rejected():
    report = _candidate()
    report["gates"][0]["passed"] = False

    with pytest.raises(RCLValidationError, match="failed evidence gates"):
        preview_intent_approval(
            _profile(),
            report,
            "interaction.post_release_hold",
            approved_at="2026-08-14T09:00:00Z",
        )


def test_action_behavior_mismatch_is_rejected():
    with pytest.raises(RCLValidationError, match="does not match behavior_id"):
        preview_intent_approval(
            _profile(),
            _candidate(),
            "interaction.some_other_behavior",
            approved_at="2026-08-14T09:00:00Z",
        )


def test_approval_timestamp_cannot_precede_candidate():
    with pytest.raises(RCLValidationError, match="cannot precede"):
        preview_intent_approval(
            _profile(),
            _candidate(),
            "interaction.post_release_hold",
            approved_at="2026-08-14T08:00:00Z",
        )


def test_apply_refuses_existing_or_nested_output(tmp_path):
    profile = _profile()
    report = _candidate()
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(RCLValidationError, match="already exists"):
        apply_intent_approval(
            profile,
            report,
            "interaction.post_release_hold",
            existing,
            approved_at="2026-08-14T09:00:00Z",
        )

    with pytest.raises(RCLValidationError, match="must not be created inside"):
        apply_intent_approval(
            profile,
            report,
            "interaction.post_release_hold",
            profile.root / "nested-output",
            approved_at="2026-08-14T09:00:00Z",
        )


def test_public_and_runtime_intent_approval_artifacts_match():
    root = _root()
    for name in ["intent-approval-patch.schema.json", "intent-approval-result.schema.json"]:
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text())
        public = json.loads((root / "spec" / "schemas" / name).read_text())
        assert runtime == public

    runtime_behavior = json.loads((root / "rcl" / "schemas" / "behavior.schema.json").read_text())
    public_behavior = json.loads((root / "spec" / "schemas" / "v0.4" / "behavior.schema.json").read_text())
    assert runtime_behavior == public_behavior


def test_cli_preview_and_apply(monkeypatch, capsys, tmp_path):
    root = _root()
    report = _candidate()
    report_path = tmp_path / "candidate.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    profile_path = root / "examples" / "intent-approval" / "object-release-before"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "approve-intent",
            "preview",
            str(profile_path),
            str(report_path),
            "interaction.post_release_hold",
            "--approved-at",
            "2026-08-14T09:00:00Z",
            "--json",
        ],
    )
    assert routed_main() == 0
    patch = json.loads(capsys.readouterr().out)
    assert patch["after_intent"]["goal_id"] == "x.rcl-demo.stabilize_released_object"

    output = tmp_path / "cli-approved"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "approve-intent",
            "apply",
            str(profile_path),
            str(report_path),
            "interaction.post_release_hold",
            str(output),
            "--approved-at",
            "2026-08-14T09:00:00Z",
            "--approved-by",
            "demo-user",
            "--json",
        ],
    )
    assert routed_main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["output_valid"] is True
    assert _behavior(RCLProfile.open(output))["intent"]["provenance"]["approved_by"] == "demo-user"
