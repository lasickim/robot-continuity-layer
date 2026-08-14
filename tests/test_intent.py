import copy
import json
import shutil
from pathlib import Path

import pytest

from rcl.intent import (
    get_intent_goal,
    load_intent_vocabulary,
    validate_behavior_intent_metadata,
)
from rcl.intent_reference_adapter import IntentReferenceAdapter
from rcl.migration import migrate_profile
from rcl.profile import RCLProfile, RCLValidationError
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "intent" / "sit-assistant-v1")


def _target() -> dict:
    return json.loads(
        (_root() / "examples" / "targets" / "intent-demo-v2.embodiment.json").read_text()
    )


def _result(report: dict, behavior_id: str) -> dict:
    return next(item for item in report["behavior_results"] if item["behavior_id"] == behavior_id)


def test_intent_reference_profile_and_vocabulary_validate():
    profile = _profile()
    profile.validate(require_manifest=False)
    vocabulary = load_intent_vocabulary()

    assert vocabulary["vocabulary_version"] == "0.1"
    assert get_intent_goal("safety.verify_sitting_area_clear") is not None
    assert get_intent_goal("interaction.optimize_handover_orientation") is not None


def test_published_intent_vocabulary_matches_packaged_copy():
    published = json.loads(
        (_root() / "spec" / "intent-vocabulary-v0.1.json").read_text(encoding="utf-8")
    )
    assert published == load_intent_vocabulary()


def test_published_v04_schemas_match_runtime_schemas():
    root = _root()
    pairs = [
        (
            root / "rcl" / "schemas" / "behavior.schema.json",
            root / "spec" / "schemas" / "v0.4" / "behavior.schema.json",
        ),
        (
            root / "rcl" / "schemas" / "migration-report.schema.json",
            root / "spec" / "schemas" / "v0.4" / "migration-report.schema.json",
        ),
    ]
    for runtime_path, published_path in pairs:
        assert json.loads(runtime_path.read_text(encoding="utf-8")) == json.loads(
            published_path.read_text(encoding="utf-8")
        )


def test_v2_preserves_goal_while_dropping_obsolete_rearward_expression():
    report = migrate_profile(
        _profile(),
        _target(),
        IntentReferenceAdapter(),
        created_at="2026-08-14T06:40:00Z",
    )
    sit = _result(report, "safety.pre_sit_clearance_check")

    assert sit["status"] == "preserved"
    assert sit["intent_result"]["status"] == "preserved"
    assert sit["intent_result"]["goal_id"] == "safety.verify_sitting_area_clear"
    assert sit["intent_result"]["target_strategy"] == "direct_rear_clearance_sensing"
    assert sit["expression_result"]["status"] == "unsupported"
    assert "perception.directional_attention" in sit["expression_result"]["missing_capabilities"]
    assert report["continuity"]["migration_success"] is True
    assert report["continuity"]["intent_required_failures"] == []


def test_handover_goal_survives_without_copying_wrist_roll():
    report = migrate_profile(_profile(), _target(), IntentReferenceAdapter())
    handover = _result(report, "interaction.present_handover")

    assert handover["status"] == "preserved"
    assert handover["intent_result"]["status"] == "preserved"
    assert handover["intent_result"]["target_strategy"] == "target_native_handover_orientation"
    assert handover["expression_result"]["status"] == "unsupported"
    assert "x.demo.wrist_roll" in handover["expression_result"]["missing_capabilities"]


def test_expression_can_be_preserved_separately_when_target_supports_it():
    target = _target()
    target["capabilities"].extend([
        "perception.directional_attention",
        "x.demo.wrist_roll",
    ])

    report = migrate_profile(_profile(), target, IntentReferenceAdapter())
    sit = _result(report, "safety.pre_sit_clearance_check")
    handover = _result(report, "interaction.present_handover")

    assert sit["intent_result"]["status"] == "preserved"
    assert sit["expression_result"]["status"] == "preserved"
    assert handover["intent_result"]["status"] == "preserved"
    assert handover["expression_result"]["status"] == "preserved"


def test_missing_required_intent_capability_forces_migration_failure():
    target = _target()
    target["capabilities"].remove("perception.sitting_area_clearance")

    report = migrate_profile(_profile(), target, IntentReferenceAdapter())
    sit = _result(report, "safety.pre_sit_clearance_check")

    assert sit["intent_result"]["status"] == "unsupported"
    assert report["continuity"]["migration_success"] is False
    assert "intent:safety.pre_sit_clearance_check" in report["continuity"]["intent_required_failures"]
    assert "intent:safety.pre_sit_clearance_check" in report["continuity"]["required_failures"]


def test_unknown_standard_goal_is_rejected():
    payload = copy.deepcopy(_profile().load("behavior.json"))
    payload["behaviors"][0]["intent"]["goal_id"] = "safety.telepathic_chair_check"

    with pytest.raises(RCLValidationError, match="unregistered standard intent goal"):
        validate_behavior_intent_metadata(payload)


def test_registered_goal_rejects_wrong_trigger():
    payload = copy.deepcopy(_profile().load("behavior.json"))
    payload["behaviors"][0]["intent"]["trigger"] = "activity.after_sit_down"

    with pytest.raises(RCLValidationError, match="is not registered"):
        validate_behavior_intent_metadata(payload)


def test_existing_v03_profile_without_intent_remains_valid():
    profile = RCLProfile.open(_root() / "examples" / "mobile-base")
    assert profile.summary()["behavior_count"] >= 1


def test_profile_diff_reports_intent_change(tmp_path):
    before_root = _root() / "examples" / "intent" / "sit-assistant-v1"
    after_root = tmp_path / "after"
    shutil.copytree(before_root, after_root)

    payload_path = after_root / "behavior.json"
    payload = json.loads(payload_path.read_text())
    payload["behaviors"][0]["intent"]["criticality"] = "preferred"
    payload_path.write_text(json.dumps(payload, indent=2) + "\n")

    before = RCLProfile.open(before_root)
    after = RCLProfile.open(after_root)
    report = diff_profiles(before, after)
    sit_change = next(
        item
        for item in report["behavior_changes"]
        if item["behavior_id"] == "safety.pre_sit_clearance_check"
    )
    field = next(
        item for item in sit_change["field_changes"] if item["field"] == "intent.criticality"
    )

    assert field["before"] == "required"
    assert field["after"] == "preferred"
