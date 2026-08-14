import copy
import json
import shutil
from pathlib import Path

import pytest

from rcl.expression_recommendation import (
    evaluate_expression_optimization_recommendations,
    load_default_expression_optimization_policy,
)
from rcl.intent_reference_adapter import IntentReferenceAdapter
from rcl.intent_success_evaluation import evaluate_observed_intent_success
from rcl.migration import migrate_profile
from rcl.profile import RCLProfile, RCLValidationError


SIT = "safety.pre_sit_clearance_check"
HANDOVER = "interaction.present_handover"


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source() -> Path:
    return _root() / "examples" / "intent" / "sit-assistant-v1"


def _target() -> dict:
    return json.loads(
        (
            _root()
            / "examples"
            / "targets"
            / "intent-demo-v2-expressive.embodiment.json"
        ).read_text(encoding="utf-8")
    )


def _profile_with_style(
    tmp_path: Path,
    *,
    significance: str,
    priority: str = "optional",
) -> RCLProfile:
    destination = tmp_path / f"profile-{significance}-{priority}"
    shutil.copytree(_source(), destination)
    behavior_path = destination / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    behavior = next(item for item in payload["behaviors"] if item["behavior_id"] == SIT)
    expression = behavior["expression"]
    expression["preservation_priority"] = priority
    expression["temporal_style"] = {
        "tempo": "deliberate" if significance == "user_valued" else "natural",
        "dwell": "brief",
        "transition": "smooth",
        "timing_policy": "preserve_style" if significance == "user_valued" else "naturalize",
        "legacy_significance": significance,
    }
    behavior_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return RCLProfile.open(destination)


def _observations(
    target: dict,
    *,
    sit_success_state: str = "satisfied",
    sit_strategy: str | None = "direct_rear_clearance_sensing",
) -> dict:
    return {
        "intent_observation_version": "0.1",
        "robot_id": "RCL-INTENT-DEMO-V2",
        "embodiment_id": target["embodiment_id"],
        "captured_at": "2026-08-15T03:20:00+09:00",
        "intent_observations": [
            {
                "observation_id": "expr-rec-sit-001",
                "behavior_id": SIT,
                "trigger": "activity.before_sit_down",
                "trigger_state": "observed",
                "success_condition": "state.sitting_area_clear",
                "success_state": sit_success_state,
                "strategy_id": sit_strategy,
                "evidence_refs": ["observation://v2/sit/target-native"],
            },
            {
                "observation_id": "expr-rec-handover-001",
                "behavior_id": HANDOVER,
                "trigger": "interaction.before_handover_release",
                "trigger_state": "observed",
                "success_condition": "state.handover_orientation_acceptable",
                "success_state": "satisfied",
                "strategy_id": "target_native_handover_orientation",
                "evidence_refs": ["observation://v2/handover/target-native"],
            },
        ],
    }


def _reports(
    profile: RCLProfile,
    *,
    sit_success_state: str = "satisfied",
    sit_strategy: str | None = "direct_rear_clearance_sensing",
):
    target = _target()
    migration = migrate_profile(
        profile,
        target,
        IntentReferenceAdapter(),
        created_at="2026-08-15T03:15:00+09:00",
    )
    success = evaluate_observed_intent_success(
        profile,
        _observations(
            target,
            sit_success_state=sit_success_state,
            sit_strategy=sit_strategy,
        ),
        created_at="2026-08-15T03:21:00+09:00",
    )
    return migration, success


def _item(report: dict, behavior_id: str) -> dict:
    return next(item for item in report["recommendations"] if item["behavior_id"] == behavior_id)


def test_default_policy_is_published_and_valid():
    runtime = load_default_expression_optimization_policy()
    published = json.loads(
        (
            _root()
            / "spec"
            / "policies"
            / "expression-optimization-recommendation-policy-v0.1.json"
        ).read_text(encoding="utf-8")
    )
    assert runtime == published
    assert runtime["policy_version"] == "0.1"
    assert runtime["decision_matrix"]["optional"]["incidental"] == "review_removal"
    assert runtime["decision_matrix"]["optional"]["user_valued"] == "retain"


def test_runtime_and_public_recommendation_schemas_match():
    root = _root()
    names = [
        "expression-optimization-recommendation-policy.schema.json",
        "expression-optimization-recommendation-report.schema.json",
    ]
    for name in names:
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        public = json.loads((root / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == public


def test_unspecified_optional_expression_gets_simplification_review_not_silent_removal():
    profile = RCLProfile.open(_source())
    migration, success = _reports(profile)
    before = copy.deepcopy(profile.load("behavior.json"))

    report = evaluate_expression_optimization_recommendations(
        profile,
        migration,
        success,
        created_at="2026-08-15T03:22:00+09:00",
    )

    sit = _item(report, SIT)
    assert sit["decision"] == "review_simplification"
    assert sit["suggested_action"] == "simplify"
    assert sit["redundancy_proven"] is False
    assert report["non_mutating"] is True
    assert report["redundancy_proven"] is False
    assert profile.load("behavior.json") == before


def test_target_inability_does_not_authorize_forgetting_expression():
    profile = RCLProfile.open(_source())
    migration, success = _reports(profile)
    report = evaluate_expression_optimization_recommendations(profile, migration, success)

    handover = _item(report, HANDOVER)
    assert handover["expression_evidence"]["migration_status"] == "unsupported"
    assert handover["decision"] == "retain"
    assert handover["suggested_action"] is None


def test_optional_incidental_expression_can_be_recommended_for_removal_review(tmp_path):
    profile = _profile_with_style(tmp_path, significance="incidental")
    migration, success = _reports(profile)
    report = evaluate_expression_optimization_recommendations(profile, migration, success)

    sit = _item(report, SIT)
    assert sit["legacy_significance"] == "incidental"
    assert sit["decision"] == "review_removal"
    assert sit["suggested_action"] == "remove"
    assert all(gate["passed"] for gate in sit["gates"])


def test_recognized_expression_prefers_simplification_review(tmp_path):
    profile = _profile_with_style(tmp_path, significance="recognized")
    migration, success = _reports(profile)
    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["decision"] == "review_simplification"


def test_user_valued_expression_is_retained_by_default(tmp_path):
    profile = _profile_with_style(tmp_path, significance="user_valued")
    migration, success = _reports(profile)
    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["decision"] == "retain"
    assert sit["suggested_action"] is None


def test_preferred_expression_never_defaults_to_removal_review(tmp_path):
    profile = _profile_with_style(
        tmp_path,
        significance="incidental",
        priority="preferred",
    )
    migration, success = _reports(profile)
    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["decision"] == "review_simplification"


def test_failed_intent_success_retains_expression(tmp_path):
    profile = _profile_with_style(tmp_path, significance="incidental")
    migration, success = _reports(profile, sit_success_state="not_satisfied")
    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["intent_evidence"]["observed_status"] == "fail"
    assert sit["decision"] == "retain"


def test_strategy_mismatch_is_inconclusive(tmp_path):
    profile = _profile_with_style(tmp_path, significance="incidental")
    migration, success = _reports(profile, sit_strategy="some_other_strategy")
    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["decision"] == "inconclusive"
    gate = next(
        gate
        for gate in sit["gates"]
        if gate["gate"] == "observed_strategy_matches_target_strategy"
    )
    assert gate["passed"] is False


def test_missing_target_strategy_is_inconclusive(tmp_path):
    profile = _profile_with_style(tmp_path, significance="incidental")
    migration, success = _reports(profile)
    migration = copy.deepcopy(migration)
    result = next(item for item in migration["behavior_results"] if item["behavior_id"] == SIT)
    result["intent_result"]["target_strategy"] = None

    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["decision"] == "inconclusive"


def test_expression_safety_block_retains_expression(tmp_path):
    profile = _profile_with_style(tmp_path, significance="incidental")
    migration, success = _reports(profile)
    migration = copy.deepcopy(migration)
    result = next(item for item in migration["behavior_results"] if item["behavior_id"] == SIT)
    result["expression_result"]["status"] = "blocked_for_safety"

    sit = _item(
        evaluate_expression_optimization_recommendations(profile, migration, success),
        SIT,
    )
    assert sit["decision"] == "retain"


def test_mismatched_target_report_is_rejected():
    profile = RCLProfile.open(_source())
    migration, success = _reports(profile)
    success = copy.deepcopy(success)
    success["observed_subject"]["embodiment_id"] = "wrong-target"

    with pytest.raises(RCLValidationError, match="target embodiment"):
        evaluate_expression_optimization_recommendations(profile, migration, success)


def test_mismatched_goal_report_is_rejected():
    profile = RCLProfile.open(_source())
    migration, success = _reports(profile)
    success = copy.deepcopy(success)
    item = next(item for item in success["intent_results"] if item["behavior_id"] == SIT)
    item["goal_id"] = "safety.other_goal"

    with pytest.raises(RCLValidationError, match="observed goal_id"):
        evaluate_expression_optimization_recommendations(profile, migration, success)


def test_recommendation_ids_are_stable_across_report_creation_time(tmp_path):
    profile = _profile_with_style(tmp_path, significance="incidental")
    migration, success = _reports(profile)
    first = evaluate_expression_optimization_recommendations(
        profile,
        migration,
        success,
        created_at="2026-08-15T03:30:00+09:00",
    )
    second = evaluate_expression_optimization_recommendations(
        profile,
        migration,
        success,
        created_at="2026-08-15T04:30:00+09:00",
    )
    assert [item["recommendation_id"] for item in first["recommendations"]] == [
        item["recommendation_id"] for item in second["recommendations"]
    ]
    assert first["created_at"] != second["created_at"]
