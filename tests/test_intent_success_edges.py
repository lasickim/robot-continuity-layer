import json
import sys
from pathlib import Path

import pytest

from rcl.cli_router import main as rcl_main
from rcl.intent_success_evaluation import evaluate_observed_intent_success
from rcl.profile import RCLProfile, RCLValidationError


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "intent" / "sit-assistant-v1")


def _observations() -> dict:
    return json.loads(
        (_root() / "examples" / "intent-observations" / "sit-assistant-v2.observations.json").read_text(encoding="utf-8")
    )


def test_duplicate_observation_id_is_rejected():
    observations = _observations()
    observations["intent_observations"][1]["observation_id"] = observations["intent_observations"][0]["observation_id"]

    with pytest.raises(RCLValidationError, match="Duplicate intent observation_id"):
        evaluate_observed_intent_success(_profile(), observations)


def test_evaluate_intent_cli_writes_report(monkeypatch, tmp_path):
    root = _root()
    output = tmp_path / "intent-success-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent",
            str(root / "examples" / "intent" / "sit-assistant-v1"),
            str(root / "examples" / "intent-observations" / "sit-assistant-v2.observations.json"),
            "--output",
            str(output),
        ],
    )

    assert rcl_main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["method"] == "rcl.observed.intent_success.v0.1"
