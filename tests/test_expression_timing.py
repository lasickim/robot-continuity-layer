import copy
import json
import shutil
from pathlib import Path

import pytest

from rcl.expression_timing import (
    realize_temporal_style,
    validate_expression_temporal_style,
)
from rcl.intent_reference_adapter import IntentReferenceAdapter
from rcl.migration import migrate_profile
from rcl.profile import RCLProfile, RCLValidationError
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _base_profile() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "intent" / "sit-assistant-v1")


def _target() -> dict:
    return json.loads(
        (_root() / "examples" / "targets" / "intent-demo-v2-expressive.embodiment.json").read_text(encoding="utf-8")
    )


def _style(name: str) -> dict:
    payload = json.loads(
        (_root() / "examples" / "expression-timing" / name).read_text(encoding="utf-8")
    )
    return payload["temporal_style"]


def _timed_profile(tmp_path: Path, style: dict) -> RCLProfile:
    source = _root() / "examples" / "intent" / "sit-assistant-v1"
    destination = tmp_path / "profile"
    shutil.copytree(source, destination)
    behavior_path = destination / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    payload["behaviors"][0]["expression"]["temporal_style"] = copy.deepcopy(style)
    behavior_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return RCLProfile.open(destination)


def _sit_result(report: dict) -> dict:
    return next(
        item
        for item in report["behavior_results"]
        if item["behavior_id"] == "safety.pre_sit_clearance_check"
    )


def test_hardware_limited_v1_timing_is_naturalized_on_v2(tmp_path):
    style = _style("naturalized-rearward-glance.json")
    profile = _timed_profile(tmp_path, style)

    report = migrate_profile(profile, _target(), IntentReferenceAdapter())
    sit = _sit_result(report)
    timing = sit["expression_timing_result"]

    assert sit["intent_result"]["target_strategy"] == "direct_rear_clearance_sensing"
    assert sit["expression_result"]["status"] == "preserved"
    assert timing["status"] == "naturalized"
    assert timing["timing_policy"] == "naturalize"
    assert timing["realized_timing"] == {
        "motion_duration_ms": 380,
        "dwell_duration_ms": 160,
        "return_duration_ms": 360,
        "transition": "smooth",
    }
    assert style["source_timing_observation"]["motion_duration_ms"] == 1400
    assert timing["realized_timing"]["motion_duration_ms"] < 1400
    assert {item["artifact"] for item in timing["source_artifacts"]} == {
        "actuator_speed_limit",
        "wiring_constraint",
    }


def test_user_valued_deliberate_tempo_is_preserved_on_v2(tmp_path):
    style = _style("deliberate-rearward-glance.json")
    profile = _timed_profile(tmp_path, style)

    report = migrate_profile(profile, _target(), IntentReferenceAdapter())
    timing = _sit_result(report)["expression_timing_result"]

    assert timing["status"] == "preserved"
    assert timing["semantic_style"]["tempo"] == "deliberate"
    assert timing["semantic_style"]["legacy_significance"] == "user_valued"
    assert timing["realized_timing"]["motion_duration_ms"] == 900
    assert timing["realized_timing"]["return_duration_ms"] == 850


def test_target_safety_bound_approximates_too_fast_tempo(tmp_path):
    style = _style("naturalized-rearward-glance.json")
    style["tempo"] = "quick"
    profile = _timed_profile(tmp_path, style)
    target = _target()
    timing_profile = target["limits"]["expression_timing_profiles"]["observation.brief_rearward_check"]
    timing_profile["tempo_duration_ms"]["quick"] = 120
    timing_profile["return_duration_ms"]["quick"] = 110

    report = migrate_profile(profile, target, IntentReferenceAdapter())
    timing = _sit_result(report)["expression_timing_result"]

    assert timing["status"] == "approximated"
    assert timing["realized_timing"]["motion_duration_ms"] == 220
    assert timing["realized_timing"]["return_duration_ms"] == 220


def test_explicit_target_safety_block_is_reported(tmp_path):
    profile = _timed_profile(tmp_path, _style("naturalized-rearward-glance.json"))
    target = _target()
    target["limits"]["expression_timing_profiles"]["observation.brief_rearward_check"]["blocked_for_safety"] = True

    report = migrate_profile(profile, target, IntentReferenceAdapter())
    timing = _sit_result(report)["expression_timing_result"]

    assert timing["status"] == "blocked_for_safety"
    assert timing["realized_timing"] is None
    assert report["continuity"]["migration_success"] is True


def test_expression_capability_loss_makes_timing_unsupported(tmp_path):
    profile = _timed_profile(tmp_path, _style("naturalized-rearward-glance.json"))
    target = _target()
    target["capabilities"].remove("perception.directional_attention")

    report = migrate_profile(profile, target, IntentReferenceAdapter())
    sit = _sit_result(report)

    assert sit["intent_result"]["status"] == "preserved"
    assert sit["expression_result"]["status"] == "unsupported"
    assert sit["expression_timing_result"]["status"] == "unsupported"
    assert sit["expression_timing_result"]["realized_timing"] is None


def test_missing_target_timing_profile_does_not_invent_milliseconds(tmp_path):
    profile = _timed_profile(tmp_path, _style("naturalized-rearward-glance.json"))
    target = _target()
    target["limits"]["expression_timing_profiles"].clear()

    report = migrate_profile(profile, target, IntentReferenceAdapter())
    sit = _sit_result(report)

    assert sit["expression_result"]["status"] == "preserved"
    assert sit["expression_timing_result"]["status"] == "unsupported"
    assert sit["expression_timing_result"]["realized_timing"] is None


def test_preserve_style_requires_non_incidental_legacy_significance():
    style = _style("deliberate-rearward-glance.json")
    style["legacy_significance"] = "incidental"

    with pytest.raises(RCLValidationError, match="preserve_style requires"):
        validate_expression_temporal_style("demo.behavior", style)


def test_source_timing_observation_can_never_be_normative():
    style = _style("naturalized-rearward-glance.json")
    style["source_timing_observation"]["normative"] = True

    with pytest.raises(RCLValidationError, match="normative=false"):
        validate_expression_temporal_style("demo.behavior", style)


def test_invalid_target_timing_bounds_are_rejected():
    style = _style("naturalized-rearward-glance.json")
    target_profile = copy.deepcopy(
        _target()["limits"]["expression_timing_profiles"]["observation.brief_rearward_check"]
    )
    target_profile["min_safe_motion_duration_ms"] = 900
    target_profile["max_safe_motion_duration_ms"] = 500

    with pytest.raises(RCLValidationError, match="minimum safe duration exceeds"):
        realize_temporal_style(style, target_profile)


def test_existing_expression_without_temporal_style_remains_backward_compatible():
    target = json.loads(
        (_root() / "examples" / "targets" / "intent-demo-v2.embodiment.json").read_text(encoding="utf-8")
    )
    report = migrate_profile(_base_profile(), target, IntentReferenceAdapter())
    sit = _sit_result(report)

    assert "expression_timing_result" not in sit
    assert sit["intent_result"]["status"] == "preserved"


def test_profile_diff_reports_temporal_style_addition(tmp_path):
    before = _base_profile()
    after = _timed_profile(tmp_path, _style("naturalized-rearward-glance.json"))

    report = diff_profiles(before, after)
    sit_change = next(
        item
        for item in report["behavior_changes"]
        if item["behavior_id"] == "safety.pre_sit_clearance_check"
    )
    timing_change = next(
        item
        for item in sit_change["field_changes"]
        if item["field"] == "expression.temporal_style"
    )

    assert timing_change["change_type"] == "added"
    assert timing_change["before"] is None
    assert timing_change["after"]["timing_policy"] == "naturalize"


def test_runtime_and_published_v04_schemas_remain_identical():
    root = _root()
    for name in ("behavior.schema.json", "migration-report.schema.json"):
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        published = json.loads((root / "spec" / "schemas" / "v0.4" / name).read_text(encoding="utf-8"))
        assert runtime == published
