import json
import shutil
import sys
from pathlib import Path

import pytest

from rcl.cli import main as rcl_main
from rcl.profile import RCLProfile, RCLValidationError, validate_schema
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _before() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "history" / "mobile-base-before")


def _after() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "history" / "mobile-base-after")


def test_reference_profile_diff_tracks_habit_promotion_and_added_behavior():
    report = diff_profiles(_before(), _after())
    validate_schema(report, "profile-diff-report")

    assert report["changed"] is True
    assert report["summary"] == {
        "added_behaviors": 1,
        "removed_behaviors": 0,
        "modified_behaviors": 1,
    }

    follow = next(
        item
        for item in report["behavior_changes"]
        if item["behavior_id"] == "navigation.follow_person"
    )
    assert follow["change_type"] == "modified"

    parameters = {item["field"]: item for item in follow["parameter_changes"]}
    assert parameters["preferred_distance_m"]["before"] == 1.36
    assert parameters["preferred_distance_m"]["after"] == 1.32
    assert parameters["stop_delay_ms"]["before"] == 380
    assert parameters["stop_delay_ms"]["after"] == 420

    fields = {item["field"]: item for item in follow["field_changes"]}
    assert fields["habit.lifecycle"]["before"] == "learning"
    assert fields["habit.lifecycle"]["after"] == "stable"
    assert fields["confidence"]["before"] == 0.82
    assert fields["confidence"]["after"] == 0.93

    event_ids = [event["event_id"] for event in follow["history_events_added"]]
    assert event_ids == ["follow-003", "follow-004"]

    added = next(
        item
        for item in report["behavior_changes"]
        if item["behavior_id"] == "navigation.pre_turn_observation"
    )
    assert added["change_type"] == "added"
    assert [event["event_id"] for event in added["history_events_added"]] == [
        "turn-001",
        "turn-002",
    ]


def test_same_profile_has_no_semantic_diff():
    report = diff_profiles(_after(), _after())
    assert report["changed"] is False
    assert report["summary"] == {
        "added_behaviors": 0,
        "removed_behaviors": 0,
        "modified_behaviors": 0,
    }
    assert report["behavior_changes"] == []


def test_reverse_diff_surfaces_removed_behavior_and_history():
    report = diff_profiles(_after(), _before())
    assert report["summary"]["removed_behaviors"] == 1
    removed = next(
        item
        for item in report["behavior_changes"]
        if item["behavior_id"] == "navigation.pre_turn_observation"
    )
    assert removed["change_type"] == "removed"
    assert removed["history_event_ids_removed"] == ["turn-001", "turn-002"]


def test_invalid_habit_chronology_is_rejected(tmp_path):
    target = tmp_path / "profile"
    shutil.copytree(_root() / "examples" / "history" / "mobile-base-after", target)
    behavior_path = target / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    follow = payload["behaviors"][0]
    follow["habit"]["stable_since"] = "2025-12-01T00:00:00Z"
    behavior_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RCLValidationError, match="stable_since cannot precede"):
        RCLProfile.open(target)


def test_duplicate_habit_event_id_is_rejected(tmp_path):
    target = tmp_path / "profile"
    shutil.copytree(_root() / "examples" / "history" / "mobile-base-after", target)
    behavior_path = target / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    events = payload["behaviors"][0]["habit"]["events"]
    events[1]["event_id"] = events[0]["event_id"]
    behavior_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RCLValidationError, match="duplicate habit event_id"):
        RCLProfile.open(target)


def test_profile_diff_cli_json(monkeypatch, capsys):
    root = _root()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "diff",
            str(root / "examples" / "history" / "mobile-base-before"),
            str(root / "examples" / "history" / "mobile-base-after"),
            "--json",
        ],
    )

    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["diff_version"] == "0.1"
    assert payload["method"] == "rcl.profile.semantic_diff.v0.1"
    assert payload["changed"] is True
    assert payload["summary"]["added_behaviors"] == 1
