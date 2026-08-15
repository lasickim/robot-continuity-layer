import json
import sys
from pathlib import Path

from rcl.cli_router import main


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "examples" / "intent" / "sit-assistant-v1"
V2_SERIES = ROOT / "examples" / "intent-series" / "sit-assistant-v2.series.json"


def _load_series():
    return json.loads(V2_SERIES.read_text(encoding="utf-8"))


def _write(path: Path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def test_repeated_intent_cli_json(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent-series",
            str(PROFILE),
            str(V2_SERIES),
            "--json",
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repeated_intent_success_version"] == "0.1"
    assert payload["observed_subject"]["series_id"] == "sit-assistant-v2-repeated"
    assert payload["status"] == "estimated"


def test_repeated_intent_cli_text(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent-series",
            str(PROFILE),
            str(V2_SERIES),
        ],
    )

    assert main() == 0
    output = capsys.readouterr().out
    assert "RCL Repeated Intent Success" in output
    assert "9 trials / 3 sessions" in output
    assert "Universal Success Threshold: NO" in output
    assert "target.direct_rear_depth_sensing" in output


def test_repeated_intent_cli_output_file(monkeypatch, capsys, tmp_path):
    output = tmp_path / "repeated-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent-series",
            str(PROFILE),
            str(V2_SERIES),
            "--output",
            str(output),
        ],
    )

    assert main() == 0
    assert capsys.readouterr().out.strip() == str(output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "estimated"
    assert payload["total_trial_count"] == 9


def test_repeated_intent_cli_inconclusive_exit(monkeypatch, tmp_path):
    series = _load_series()
    series["sessions"] = [series["sessions"][0]]
    series["sessions"][0]["trials"] = series["sessions"][0]["trials"][:2]
    path = _write(tmp_path / "inconclusive.json", series)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent-series",
            str(PROFILE),
            str(path),
            "--json",
        ],
    )

    assert main() == 7


def test_repeated_intent_cli_required_failure_exit(monkeypatch, tmp_path):
    series = _load_series()
    series["sessions"][0]["trials"][0]["intent_observations"][0]["success_state"] = "not_satisfied"
    path = _write(tmp_path / "failed.json", series)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent-series",
            str(PROFILE),
            str(path),
            "--json",
        ],
    )

    assert main() == 8


def test_repeated_intent_cli_validation_error_exit(monkeypatch, tmp_path, capsys):
    series = _load_series()
    series["sessions"][1]["session_id"] = series["sessions"][0]["session_id"]
    path = _write(tmp_path / "invalid.json", series)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-intent-series",
            str(PROFILE),
            str(path),
        ],
    )

    assert main() == 2
    assert "ERROR:" in capsys.readouterr().out
