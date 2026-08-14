import json
import shutil
import sys
from pathlib import Path

import pytest

from rcl.cli import main as rcl_main
from rcl.evaluation import evaluate_observed_continuity
from rcl.profile import RCLProfile, RCLValidationError, validate_schema


def _fixtures():
    root = Path(__file__).resolve().parents[1]
    profile = RCLProfile.open(root / "examples" / "mobile-base")
    observations = json.loads(
        (root / "examples" / "observations" / "demo-rover-b.observations.json").read_text(
            encoding="utf-8"
        )
    )
    return root, profile, observations


def _evaluate(observations):
    _, profile, _ = _fixtures()
    return evaluate_observed_continuity(
        profile,
        observations,
        created_at="2026-08-14T00:45:00Z",
    )


def test_reference_observations_are_within_declared_tolerance():
    _, _, observations = _fixtures()
    report = _evaluate(observations)

    validate_schema(report, "observed-evaluation-report")
    assert report["score"] == 100.0
    assert report["evaluation_success"] is True
    assert report["status"] == "within_tolerance"
    assert report["required_failures"] == []
    assert [item["status"] for item in report["metric_results"]] == [
        "within_tolerance",
        "within_tolerance",
    ]


def test_metric_outside_tolerance_receives_linear_partial_credit():
    _, _, observations = _fixtures()
    observations["behavior_observations"][0]["metrics"]["following_distance_m"] = 1.55

    report = _evaluate(observations)
    distance = report["metric_results"][0]

    assert distance["absolute_error"] == 0.15
    assert distance["similarity"] == 0.75
    assert distance["status"] == "partial"
    assert report["score"] == 83.33
    assert report["evaluation_success"] is True
    assert report["status"] == "degraded"


def test_required_metric_at_zero_credit_fails_observed_evaluation():
    _, _, observations = _fixtures()
    observations["behavior_observations"][0]["metrics"]["following_distance_m"] = 1.75

    report = _evaluate(observations)
    distance = report["metric_results"][0]

    assert distance["similarity"] == 0.0
    assert distance["status"] == "outside_limit"
    assert report["score"] == 33.33
    assert report["evaluation_success"] is False
    assert report["status"] == "failed"
    assert report["required_failures"] == [
        "navigation.follow_person.following_distance"
    ]


def test_missing_required_observation_is_explicit_and_fails():
    _, _, observations = _fixtures()
    del observations["behavior_observations"][0]["metrics"]["following_distance_m"]

    report = _evaluate(observations)
    distance = report["metric_results"][0]

    assert distance["observed"] is None
    assert distance["status"] == "missing"
    assert distance["similarity"] == 0.0
    assert report["score"] == 33.33
    assert report["evaluation_success"] is False


def test_missing_optional_observation_is_visible_but_not_scored():
    _, _, observations = _fixtures()
    del observations["behavior_observations"][0]["metrics"]["stop_delay_ms"]

    report = _evaluate(observations)
    stop_delay = report["metric_results"][1]

    assert stop_delay["status"] == "missing_optional"
    assert stop_delay["similarity"] is None
    assert report["score"] == 100.0
    assert report["evaluation_success"] is True


def test_profile_validation_rejects_unknown_evaluation_target_parameter(tmp_path):
    root, _, _ = _fixtures()
    copied = tmp_path / "profile"
    shutil.copytree(root / "examples" / "mobile-base", copied)

    behavior_path = copied / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    payload["behaviors"][0]["evaluation"]["metrics"][0]["target_parameter"] = "does_not_exist"
    behavior_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RCLValidationError, match="does not exist"):
        RCLProfile.open(copied)


def test_profile_validation_rejects_invalid_tolerance_falloff(tmp_path):
    root, _, _ = _fixtures()
    copied = tmp_path / "profile"
    shutil.copytree(root / "examples" / "mobile-base", copied)

    behavior_path = copied / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    metric = payload["behaviors"][0]["evaluation"]["metrics"][0]
    metric["zero_credit_at"] = metric["tolerance"]
    behavior_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RCLValidationError, match="greater than tolerance"):
        RCLProfile.open(copied)


def test_evaluate_cli_json_output(monkeypatch, capsys):
    root, _, _ = _fixtures()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate",
            str(root / "examples" / "mobile-base"),
            str(root / "examples" / "observations" / "demo-rover-b.observations.json"),
            "--json",
        ],
    )

    assert rcl_main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["score"] == 100.0
    assert report["status"] == "within_tolerance"
    assert report["method"] == "rcl.observed.numeric_tolerance.v0.1"
