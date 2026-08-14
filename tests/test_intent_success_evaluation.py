import copy
import json
from pathlib import Path

import pytest

from rcl.intent_success_evaluation import (
    INTENT_SUCCESS_EVALUATION_METHOD,
    evaluate_observed_intent_success,
)
from rcl.profile import RCLProfile, RCLValidationError, validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "intent" / "sit-assistant-v1")


def _observations(name: str) -> dict:
    return json.loads(
        (_root() / "examples" / "intent-observations" / name).read_text(encoding="utf-8")
    )


def _result(report: dict, behavior_id: str) -> dict:
    return next(item for item in report["intent_results"] if item["behavior_id"] == behavior_id)


def test_source_and_target_native_strategies_both_pass_same_declared_intents():
    v1 = evaluate_observed_intent_success(
        _profile(), _observations("sit-assistant-v1.observations.json"), created_at="2026-08-15T01:10:00Z"
    )
    v2 = evaluate_observed_intent_success(
        _profile(), _observations("sit-assistant-v2.observations.json"), created_at="2026-08-15T01:10:00Z"
    )

    assert v1["method"] == INTENT_SUCCESS_EVALUATION_METHOD
    assert v1["status"] == "passed"
    assert v2["status"] == "passed"
    assert v1["evaluation_success"] is True
    assert v2["evaluation_success"] is True
    assert _result(v1, "safety.pre_sit_clearance_check")["strategy_id"] != _result(
        v2, "safety.pre_sit_clearance_check"
    )["strategy_id"]
    assert _result(v1, "safety.pre_sit_clearance_check")["status"] == "pass"
    assert _result(v2, "safety.pre_sit_clearance_check")["status"] == "pass"


def test_required_intent_failure_fails_overall_report():
    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"][0]["success_state"] = "not_satisfied"

    report = evaluate_observed_intent_success(_profile(), observations)

    assert report["status"] == "failed"
    assert report["evaluation_success"] is False
    assert report["required_failures"] == ["safety.pre_sit_clearance_check"]
    assert _result(report, "safety.pre_sit_clearance_check")["status"] == "fail"


def test_required_not_observable_is_inconclusive():
    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"][0]["success_state"] = "not_observable"

    report = evaluate_observed_intent_success(_profile(), observations)

    assert report["status"] == "inconclusive"
    assert report["evaluation_success"] is None
    assert report["required_inconclusive"] == ["safety.pre_sit_clearance_check"]


def test_required_not_triggered_is_inconclusive():
    observations = _observations("sit-assistant-v2.observations.json")
    item = observations["intent_observations"][0]
    item["trigger_state"] = "not_observed"
    item["success_state"] = "not_observable"

    report = evaluate_observed_intent_success(_profile(), observations)

    assert report["status"] == "inconclusive"
    assert _result(report, "safety.pre_sit_clearance_check")["status"] == "not_triggered"


def test_preferred_failure_is_explicit_but_nonblocking():
    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"][1]["success_state"] = "not_satisfied"

    report = evaluate_observed_intent_success(_profile(), observations)

    assert report["status"] == "passed"
    assert report["evaluation_success"] is True
    assert report["nonblocking_failures"] == ["interaction.present_handover"]
    assert _result(report, "interaction.present_handover")["blocking"] is False


def test_missing_required_observation_is_explicitly_inconclusive():
    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"] = [observations["intent_observations"][1]]

    report = evaluate_observed_intent_success(_profile(), observations)
    result = _result(report, "safety.pre_sit_clearance_check")

    assert report["status"] == "inconclusive"
    assert result["status"] == "not_observable"
    assert result["observation_present"] is False
    assert result["reason"] == "missing_observation"


def test_declared_trigger_and_success_condition_must_match_exactly():
    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"][0]["trigger"] = "activity.some_other_trigger"
    with pytest.raises(RCLValidationError, match="does not match declared trigger"):
        evaluate_observed_intent_success(_profile(), observations)

    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"][0]["success_condition"] = "state.some_other_condition"
    with pytest.raises(RCLValidationError, match="does not match declared success_condition"):
        evaluate_observed_intent_success(_profile(), observations)


def test_duplicate_behavior_observations_are_rejected():
    observations = _observations("sit-assistant-v2.observations.json")
    duplicate = copy.deepcopy(observations["intent_observations"][0])
    duplicate["observation_id"] = "another-observation-id"
    observations["intent_observations"].append(duplicate)

    with pytest.raises(RCLValidationError, match="Duplicate intent observation for behavior"):
        evaluate_observed_intent_success(_profile(), observations)


def test_success_cannot_be_claimed_when_trigger_was_not_observed():
    observations = _observations("sit-assistant-v2.observations.json")
    observations["intent_observations"][0]["trigger_state"] = "not_observed"

    with pytest.raises(RCLValidationError, match="must be not_observable"):
        evaluate_observed_intent_success(_profile(), observations)


def test_evaluation_is_deterministic_and_does_not_mutate_input():
    observations = _observations("sit-assistant-v2.observations.json")
    before = copy.deepcopy(observations)
    first = evaluate_observed_intent_success(
        _profile(), observations, created_at="2026-08-15T01:10:00Z"
    )
    second = evaluate_observed_intent_success(
        _profile(), observations, created_at="2026-08-15T01:10:00Z"
    )

    assert observations == before
    assert first == second
    validate_schema(first, "observed-intent-success-report")


def test_public_and_runtime_intent_success_schemas_match():
    root = _root()
    for name in ("intent-observations.schema.json", "observed-intent-success-report.schema.json"):
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        published = json.loads((root / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == published
