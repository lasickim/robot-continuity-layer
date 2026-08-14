import json
import math
import sys
from pathlib import Path

from rcl.cli import main as rcl_main
from rcl.experiment_context import compare_experiment_context
from rcl.profile import RCLProfile, validate_schema
from rcl.statistical_evaluation import compare_trial_distributions, wasserstein_1d


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    profile = RCLProfile(_root() / "examples" / "mobile-base")
    profile.validate(require_manifest=False)
    return profile


def _trial_payload(
    robot_id: str,
    distance,
    delay=None,
    *,
    context_overrides=None,
    protocol_version="0.1",
    comparison_fields=None,
):
    metrics = {"following_distance_m": list(distance)}
    if delay is not None:
        metrics["stop_delay_ms"] = list(delay)
    context = {
        "session_id": f"{robot_id.lower()}-session",
        "task_id": "follow-person-straight-5m",
        "environment_id": "test-lab-layout-01",
        "subject_ref": "subject-01",
        "start_condition_id": "stationary-2m-behind-subject",
        "software_ref": f"{robot_id.lower()}-software@1",
        "adapter_ref": f"{robot_id.lower()}-adapter@1",
        "sensor_config_ref": f"{robot_id.lower()}-sensors@1",
    }
    if context_overrides:
        for key, value in context_overrides.items():
            if value is None:
                context.pop(key, None)
            else:
                context[key] = value
    protocol = {
        "protocol_id": "rcl.person_following.baseline",
        "protocol_version": protocol_version,
        "comparison_fields": comparison_fields
        or ["task_id", "environment_id", "subject_ref", "start_condition_id"],
    }
    return {
        "trial_observation_version": "0.2",
        "robot_id": robot_id,
        "embodiment_id": f"{robot_id.lower()}-embodiment",
        "captured_at": "2026-08-14T03:10:00Z",
        "experiment": {"protocol": protocol, "context": context},
        "behavior_trials": [
            {"behavior_id": "navigation.follow_person", "metrics": metrics}
        ],
    }


def test_reference_trial_fixtures_match_with_full_score():
    root = _root()
    source = json.loads((root / "examples" / "trials" / "demo-rover-a.trials.json").read_text())
    target = json.loads((root / "examples" / "trials" / "demo-rover-b.trials.json").read_text())
    report = compare_trial_distributions(
        _profile(), source, target, created_at="2026-08-14T03:15:00Z"
    )
    validate_schema(report, "statistical-continuity-report")
    assert report["context_comparison"]["compatible"] is True
    assert report["score"] == 100.0
    assert report["evaluation_success"] is True
    assert report["status"] == "matched"
    assert report["required_failures"] == []
    assert all(item["status"] == "distribution_within_tolerance" for item in report["metric_results"])


def test_wasserstein_supports_unequal_sample_counts_exactly():
    distance = wasserstein_1d([0.0, 1.0], [0.0, 0.5, 1.0])
    assert math.isclose(distance, 1.0 / 6.0, rel_tol=1e-12, abs_tol=1e-12)


def test_same_mean_but_different_distribution_is_degraded():
    source = _trial_payload("A", [1.4, 1.4, 1.4, 1.4, 1.4])
    target = _trial_payload("B", [1.2, 1.2, 1.4, 1.6, 1.6])
    report = compare_trial_distributions(_profile(), source, target)
    result = next(item for item in report["metric_results"] if item["metric_id"] == "following_distance")
    assert result["source_mean"] == 1.4
    assert result["target_mean"] == 1.4
    assert math.isclose(result["wasserstein_distance"], 0.16, abs_tol=1e-9)
    assert math.isclose(result["similarity"], 0.7, abs_tol=1e-9)
    assert result["status"] == "distribution_partial"
    assert report["score"] == 70.0
    assert report["evaluation_success"] is True
    assert report["status"] == "degraded"


def test_large_distribution_shift_zeroes_required_metric():
    source = _trial_payload("A", [1.4] * 5)
    target = _trial_payload("B", [1.8] * 5)
    report = compare_trial_distributions(_profile(), source, target)
    result = next(item for item in report["metric_results"] if item["metric_id"] == "following_distance")
    assert math.isclose(result["wasserstein_distance"], 0.4, abs_tol=1e-9)
    assert result["similarity"] == 0.0
    assert result["status"] == "distribution_outside_limit"
    assert report["evaluation_success"] is False
    assert report["status"] == "failed"
    assert "navigation.follow_person.following_distance" in report["required_failures"]


def test_insufficient_required_trials_fail_explicitly():
    source = _trial_payload("A", [1.38, 1.39, 1.40, 1.41])
    target = _trial_payload("B", [1.38, 1.39, 1.40, 1.41, 1.42])
    report = compare_trial_distributions(_profile(), source, target)
    result = next(item for item in report["metric_results"] if item["metric_id"] == "following_distance")
    assert result["status"] == "insufficient_source"
    assert result["source_count"] == 4
    assert result["target_count"] == 5
    assert result["similarity"] == 0.0
    assert report["evaluation_success"] is False


def test_missing_optional_trials_do_not_silently_earn_credit():
    source = _trial_payload("A", [1.36, 1.38, 1.40, 1.42, 1.44])
    target = _trial_payload("B", [1.37, 1.39, 1.41, 1.43, 1.45])
    report = compare_trial_distributions(_profile(), source, target)
    optional = next(item for item in report["metric_results"] if item["metric_id"] == "stop_delay")
    assert optional["status"] == "missing_both"
    assert optional["similarity"] is None
    assert report["score"] == 100.0
    assert report["evaluation_success"] is True


def test_required_environment_mismatch_blocks_scoring():
    source = _trial_payload("A", [1.4] * 5)
    target = _trial_payload(
        "B", [1.4] * 5, context_overrides={"environment_id": "different-room"}
    )
    report = compare_trial_distributions(_profile(), source, target)
    assert report["context_comparison"]["compatible"] is False
    assert report["score"] is None
    assert report["status"] == "context_mismatch"
    assert report["metric_results"] == []
    assert "context.environment_id" in report["required_failures"]


def test_missing_required_context_field_blocks_scoring():
    source = _trial_payload("A", [1.4] * 5)
    target = _trial_payload("B", [1.4] * 5, context_overrides={"subject_ref": None})
    report = compare_trial_distributions(_profile(), source, target)
    mismatch = next(item for item in report["context_comparison"]["mismatches"] if item["field"] == "subject_ref")
    assert mismatch["reason"] == "missing_target"
    assert report["score"] is None


def test_informational_robot_metadata_can_differ_without_blocking():
    source = _trial_payload("A", [1.4] * 5)
    target = _trial_payload("B", [1.4] * 5)
    context = compare_experiment_context(source, target)
    assert context["compatible"] is True
    fields = {item["field"] for item in context["informational_differences"]}
    assert {"software_ref", "adapter_ref", "sensor_config_ref"}.issubset(fields)


def test_protocol_version_mismatch_blocks_scoring():
    source = _trial_payload("A", [1.4] * 5, protocol_version="0.1")
    target = _trial_payload("B", [1.4] * 5, protocol_version="0.2")
    report = compare_trial_distributions(_profile(), source, target)
    assert report["status"] == "context_mismatch"
    assert report["score"] is None
    assert "context.protocol_version" in report["required_failures"]


def test_compare_trials_cli_json(monkeypatch, capsys):
    root = _root()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "compare-trials",
            str(root / "examples" / "mobile-base"),
            str(root / "examples" / "trials" / "demo-rover-a.trials.json"),
            str(root / "examples" / "trials" / "demo-rover-b.trials.json"),
            "--json",
        ],
    )
    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evaluation_version"] == "0.2"
    assert payload["method"] == "rcl.observed.empirical_wasserstein.v0.2"
    assert payload["context_comparison"]["compatible"] is True
    assert payload["score"] == 100.0
    assert payload["status"] == "matched"
