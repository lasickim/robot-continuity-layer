import copy
import json
import sys
from pathlib import Path

import pytest

from rcl.cli_router import main as routed_main
from rcl.habit_approval import apply_habit_approval, preview_habit_approval
from rcl.habit_policy import evaluate_habit_promotion_candidates, load_default_habit_promotion_policy
from rcl.profile import PAYLOADS, RCLProfile, RCLValidationError, validate_schema
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile(name: str) -> RCLProfile:
    profile = RCLProfile(_root() / "examples" / "history" / name)
    profile.validate(require_manifest=False)
    return profile


def _session_report() -> dict:
    return json.loads(
        (_root() / "examples" / "policy" / "demo-follow-person.session-report.json").read_text()
    )


def _stable_candidate(profile: RCLProfile | None = None) -> dict:
    return evaluate_habit_promotion_candidates(
        profile or _profile("mobile-base-before"),
        _session_report(),
        as_of="2026-08-14T05:20:00Z",
        created_at="2026-08-14T05:21:00Z",
    )


def _legacy_candidate() -> tuple[RCLProfile, dict]:
    profile = _profile("mobile-base-after")
    policy = load_default_habit_promotion_policy()
    legacy = policy["transitions"]["stable_to_legacy"]
    legacy["min_stable_days"] = 30
    legacy["evidence"]["min_scorable_sessions"] = 3
    report = evaluate_habit_promotion_candidates(
        profile,
        _session_report(),
        policy=policy,
        as_of="2026-08-14T05:20:00Z",
        created_at="2026-08-14T05:21:00Z",
    )
    return profile, report


def _behavior(profile: RCLProfile, behavior_id: str) -> dict:
    return next(
        item for item in profile.load("behavior.json")["behaviors"]
        if item["behavior_id"] == behavior_id
    )


def test_preview_stable_approval_is_deterministic_and_non_mutating():
    profile = _profile("mobile-base-before")
    before = copy.deepcopy(profile.load("behavior.json"))
    report = _stable_candidate(profile)

    first = preview_habit_approval(
        profile,
        report,
        "navigation.follow_person",
        approved_at="2026-08-14T06:00:00Z",
        approved_by="demo-user",
    )
    second = preview_habit_approval(
        profile,
        report,
        "navigation.follow_person",
        approved_at="2026-08-14T06:00:00Z",
        approved_by="demo-user",
    )

    validate_schema(first, "habit-approval-patch")
    assert first == second
    assert first["from_lifecycle"] == "learning"
    assert first["to_lifecycle"] == "stable"
    assert first["history_event"]["event_type"] == "promotion_approved"
    assert {item["path"] for item in first["changes"]} == {
        "habit.lifecycle",
        "habit.stable_since",
        "habit.user_confirmed_at",
    }
    assert profile.load("behavior.json") == before


def test_apply_creates_new_valid_snapshot_without_changing_source(tmp_path):
    profile = _profile("mobile-base-before")
    source_bytes = {name: (profile.root / name).read_bytes() for name in PAYLOADS}
    source_params = copy.deepcopy(_behavior(profile, "navigation.follow_person")["parameters"])
    report = _stable_candidate(profile)
    output = tmp_path / "approved-profile"

    result = apply_habit_approval(
        profile,
        report,
        "navigation.follow_person",
        output,
        approved_at="2026-08-14T06:00:00Z",
        approved_by="demo-user",
    )

    validate_schema(result, "habit-approval-result")
    assert output.exists()
    assert (output / "manifest.json").exists()
    assert result["source_unchanged"] is True
    assert result["output_valid"] is True
    assert result["diff_summary"] == {
        "added_behaviors": 0,
        "removed_behaviors": 0,
        "modified_behaviors": 1,
    }
    assert {name: (profile.root / name).read_bytes() for name in PAYLOADS} == source_bytes

    approved = RCLProfile.open(output)
    behavior = _behavior(approved, "navigation.follow_person")
    assert behavior["parameters"] == source_params
    assert behavior["habit"]["lifecycle"] == "stable"
    assert behavior["habit"]["stable_since"] == "2026-08-14T06:00:00Z"
    assert behavior["habit"]["user_confirmed_at"] == "2026-08-14T06:00:00Z"
    assert behavior["habit"]["events"][-1]["event_type"] == "promotion_approved"

    diff = diff_profiles(profile, approved)
    assert diff["summary"]["modified_behaviors"] == 1
    assert diff["behavior_changes"][0]["parameter_changes"] == []


def test_apply_refuses_existing_output_directory(tmp_path):
    profile = _profile("mobile-base-before")
    output = tmp_path / "already-there"
    output.mkdir()

    with pytest.raises(RCLValidationError, match="already exists"):
        apply_habit_approval(
            profile,
            _stable_candidate(profile),
            "navigation.follow_person",
            output,
            approved_at="2026-08-14T06:00:00Z",
        )


def test_blocked_promotion_decision_cannot_be_approved():
    profile = _profile("mobile-base-before")
    evidence = _session_report()
    evidence["evaluation_success"] = False
    evidence["status"] = "session_failures"
    evidence["failed_session_count"] = 1
    evidence["failed_session_ids"] = ["day-2"]
    report = evaluate_habit_promotion_candidates(
        profile,
        evidence,
        as_of="2026-08-14T05:20:00Z",
        created_at="2026-08-14T05:21:00Z",
    )

    with pytest.raises(RCLValidationError, match="not an eligible candidate"):
        preview_habit_approval(
            profile,
            report,
            "navigation.follow_person",
            approved_at="2026-08-14T06:00:00Z",
        )


def test_stale_promotion_report_cannot_be_applied_to_different_lifecycle():
    report = _stable_candidate()
    stable_profile = _profile("mobile-base-after")

    with pytest.raises(RCLValidationError, match="does not match promotion report"):
        preview_habit_approval(
            stable_profile,
            report,
            "navigation.follow_person",
            approved_at="2026-08-14T06:00:00Z",
        )


def test_approval_timestamp_must_follow_evidence_and_history():
    profile = _profile("mobile-base-before")
    with pytest.raises(RCLValidationError, match="cannot precede"):
        preview_habit_approval(
            profile,
            _stable_candidate(profile),
            "navigation.follow_person",
            approved_at="2026-03-02T00:00:00Z",
        )


def test_explicit_legacy_approval_creates_legacy_snapshot(tmp_path):
    profile, report = _legacy_candidate()
    output = tmp_path / "legacy-profile"

    result = apply_habit_approval(
        profile,
        report,
        "navigation.follow_person",
        output,
        approved_at="2026-08-14T06:00:00Z",
        approved_by="demo-user",
    )

    assert result["from_lifecycle"] == "stable"
    assert result["to_lifecycle"] == "legacy"
    approved = RCLProfile.open(output)
    habit = _behavior(approved, "navigation.follow_person")["habit"]
    assert habit["lifecycle"] == "legacy"
    assert habit["legacy_since"] == "2026-08-14T06:00:00Z"
    assert habit["user_confirmed_at"] == "2026-07-15T00:00:00Z"
    assert habit["events"][-1]["event_type"] == "promotion_approved"


def test_cli_router_preview_and_apply(monkeypatch, capsys, tmp_path):
    root = _root()
    profile = _profile("mobile-base-before")
    promotion = _stable_candidate(profile)
    promotion_path = tmp_path / "promotion.json"
    promotion_path.write_text(json.dumps(promotion), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "approve-habit",
            "preview",
            str(root / "examples" / "history" / "mobile-base-before"),
            str(promotion_path),
            "navigation.follow_person",
            "--approved-at",
            "2026-08-14T06:00:00Z",
            "--json",
        ],
    )
    assert routed_main() == 0
    patch = json.loads(capsys.readouterr().out)
    assert patch["to_lifecycle"] == "stable"

    output = tmp_path / "cli-approved"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "approve-habit",
            "apply",
            str(root / "examples" / "history" / "mobile-base-before"),
            str(promotion_path),
            "navigation.follow_person",
            str(output),
            "--approved-at",
            "2026-08-14T06:00:00Z",
            "--approved-by",
            "demo-user",
            "--json",
        ],
    )
    assert routed_main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["output_valid"] is True
    assert RCLProfile.open(output).load("behavior.json")["behaviors"][0]["habit"]["lifecycle"] == "stable"
