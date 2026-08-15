import copy
import json
from pathlib import Path

import pytest

from rcl import (
    RCLProfile,
    RCLValidationError,
    evaluate_repeated_intent_success,
    wilson_interval_95,
)
from rcl.profile import validate_schema


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "examples" / "intent" / "sit-assistant-v1"
V1_SERIES = ROOT / "examples" / "intent-series" / "sit-assistant-v1.series.json"
V2_SERIES = ROOT / "examples" / "intent-series" / "sit-assistant-v2.series.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(report, behavior_id):
    return next(item for item in report["intent_summaries"] if item["behavior_id"] == behavior_id)


def test_wilson_interval_matches_known_binomial_case():
    interval = wilson_interval_95(19, 20)
    assert interval == {
        "low": 0.763869,
        "high": 0.991119,
        "half_width": 0.113625,
    }
    assert wilson_interval_95(0, 0) is None


def test_v1_repeated_series_estimates_same_intents_with_source_strategies():
    report = evaluate_repeated_intent_success(
        RCLProfile.open(PROFILE),
        _load(V1_SERIES),
        created_at="2026-08-18T00:00:00Z",
    )

    validate_schema(report, "repeated-intent-success-report")
    assert report["status"] == "estimated"
    assert report["evaluation_success"] is True
    assert report["total_session_count"] == 3
    assert report["total_trial_count"] == 9

    sit = _summary(report, "safety.pre_sit_clearance_check")
    assert sit["pass_count"] == 9
    assert sit["fail_count"] == 0
    assert sit["observed_success_rate"] == 1.0
    assert sit["wilson_interval_95"]["low"] == 0.700855
    assert sit["observed_strategy_ids"] == ["source.rearward_body_observation"]
    assert sit["mean_session_success_rate"] == 1.0
    assert sit["session_success_rate_std"] == 0.0
    assert sit["session_confidence_interval_95"]["low"] == 1.0
    assert sit["session_confidence_interval_95"]["high"] == 1.0


def test_v2_repeated_series_preserves_same_intents_with_target_native_strategies():
    report = evaluate_repeated_intent_success(
        RCLProfile.open(PROFILE),
        _load(V2_SERIES),
        created_at="2026-08-18T00:00:00Z",
    )

    assert report["status"] == "estimated"
    sit = _summary(report, "safety.pre_sit_clearance_check")
    handover = _summary(report, "interaction.present_handover")
    assert sit["observed_success_rate"] == 1.0
    assert handover["observed_success_rate"] == 1.0
    assert sit["observed_strategy_ids"] == ["target.direct_rear_depth_sensing"]
    assert handover["observed_strategy_ids"] == ["target.native_handover_orientation"]


def test_required_failure_remains_blocking_even_with_high_average_success():
    series = _load(V2_SERIES)
    series["sessions"][0]["trials"][0]["intent_observations"][0]["success_state"] = "not_satisfied"

    report = evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)
    sit = _summary(report, "safety.pre_sit_clearance_check")

    assert sit["pass_count"] == 8
    assert sit["fail_count"] == 1
    assert sit["observed_success_rate"] == 0.888889
    assert sit["status"] == "observed_failures"
    assert sit["blocking"] is True
    assert report["status"] == "failed"
    assert report["evaluation_success"] is False
    assert report["required_failures"] == ["safety.pre_sit_clearance_check"]


def test_insufficient_required_observable_trials_is_inconclusive():
    series = _load(V2_SERIES)
    series["sessions"] = [series["sessions"][0]]
    series["sessions"][0]["trials"] = series["sessions"][0]["trials"][:2]

    report = evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)

    assert report["total_trial_count"] == 2
    assert report["status"] == "inconclusive"
    assert report["evaluation_success"] is None
    assert report["required_inconclusive"] == ["safety.pre_sit_clearance_check"]


def test_preferred_failure_is_explicit_but_nonblocking():
    series = _load(V2_SERIES)
    series["sessions"][1]["trials"][1]["intent_observations"][1]["success_state"] = "not_satisfied"

    report = evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)
    handover = _summary(report, "interaction.present_handover")

    assert report["status"] == "estimated"
    assert report["evaluation_success"] is True
    assert report["nonblocking_failures"] == ["interaction.present_handover"]
    assert handover["fail_count"] == 1
    assert handover["status"] == "observed_failures"
    assert handover["blocking"] is False


def test_not_observable_and_not_triggered_are_excluded_from_success_rate_denominator():
    series = _load(V2_SERIES)
    first = series["sessions"][0]["trials"][0]["intent_observations"][0]
    first["success_state"] = "not_observable"
    second = series["sessions"][0]["trials"][1]["intent_observations"][0]
    second["trigger_state"] = "not_observed"
    second["success_state"] = "not_observable"

    report = evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)
    sit = _summary(report, "safety.pre_sit_clearance_check")

    assert sit["pass_count"] == 7
    assert sit["fail_count"] == 0
    assert sit["not_observable_count"] == 1
    assert sit["not_triggered_count"] == 1
    assert sit["observable_trial_count"] == 7
    assert sit["observed_success_rate"] == 1.0
    assert report["status"] == "estimated"


def test_missing_observation_is_preserved_as_explicit_inconclusive_evidence():
    series = _load(V2_SERIES)
    trial = series["sessions"][0]["trials"][0]
    trial["intent_observations"] = [
        item for item in trial["intent_observations"]
        if item["behavior_id"] != "safety.pre_sit_clearance_check"
    ]

    report = evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)
    sit = _summary(report, "safety.pre_sit_clearance_check")

    assert sit["not_observable_count"] == 1
    assert sit["missing_observation_count"] == 1
    assert sit["observable_trial_count"] == 8
    assert sit["observed_success_rate"] == 1.0


def test_duplicate_series_ids_are_rejected():
    series = _load(V2_SERIES)
    series["sessions"][1]["trials"][0]["trial_id"] = series["sessions"][0]["trials"][0]["trial_id"]
    with pytest.raises(RCLValidationError, match="Duplicate intent-series trial_id"):
        evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)

    series = _load(V2_SERIES)
    duplicate = series["sessions"][0]["trials"][0]["intent_observations"][0]["observation_id"]
    series["sessions"][1]["trials"][0]["intent_observations"][0]["observation_id"] = duplicate
    with pytest.raises(RCLValidationError, match="Duplicate intent-series observation_id"):
        evaluate_repeated_intent_success(RCLProfile.open(PROFILE), series)


def test_repeated_evaluation_is_non_mutating_and_deterministic_except_created_at():
    profile = RCLProfile.open(PROFILE)
    series = _load(V2_SERIES)
    original = copy.deepcopy(series)
    behavior_before = profile.load("behavior.json")

    first = evaluate_repeated_intent_success(
        profile, series, created_at="2026-08-18T00:00:00Z"
    )
    second = evaluate_repeated_intent_success(
        profile, series, created_at="2026-08-18T00:00:00Z"
    )

    assert first == second
    assert series == original
    assert profile.load("behavior.json") == behavior_before


def test_runtime_and_public_repeated_intent_schemas_match():
    for name in (
        "intent-observation-series.schema.json",
        "repeated-intent-success-report.schema.json",
    ):
        runtime = json.loads((ROOT / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert runtime == public
