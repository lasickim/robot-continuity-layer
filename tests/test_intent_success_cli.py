import json
import sys
from pathlib import Path

from rcl.cli_router import main as rcl_main


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_evaluate_intent_cli_json(monkeypatch, capsys):
    root = _root()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent",
            str(root / "examples" / "intent" / "sit-assistant-v1"),
            str(root / "examples" / "intent-observations" / "sit-assistant-v2.observations.json"),
            "--json",
        ],
    )

    assert rcl_main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["observed_subject"]["embodiment_id"] == "intent-demo-v2-humanoid"
    assert all(item["status"] == "pass" for item in report["intent_results"])


def test_evaluate_intent_cli_inconclusive_exit_code(monkeypatch, tmp_path):
    root = _root()
    observations = json.loads(
        (root / "examples" / "intent-observations" / "sit-assistant-v2.observations.json").read_text(encoding="utf-8")
    )
    observations["intent_observations"][0]["success_state"] = "not_observable"
    path = tmp_path / "inconclusive.json"
    path.write_text(json.dumps(observations), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["rcl", "evaluate-intent", str(root / "examples" / "intent" / "sit-assistant-v1"), str(path), "--json"],
    )
    assert rcl_main() == 7
