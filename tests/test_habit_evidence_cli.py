import json
import sys
from pathlib import Path

from rcl.cli_entry import main
from rcl.experience import compact_experience


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "examples" / "experience" / "habit-follow-person.episodes.json"


def _store():
    return json.loads(STORE.read_text(encoding="utf-8"))


def test_raw_habit_evidence_cli_json(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-habit-evidence",
            str(STORE),
            "navigation.follow_person",
            "--created-at",
            "2026-02-01T00:00:00Z",
            "--json",
        ],
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["evidence_basis"] == "raw"
    assert report["status"] == "sufficient"
    assert report["pseudo_episodes_created"] is False


def test_summary_habit_evidence_cli_can_raw_verify(monkeypatch, capsys, tmp_path):
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(compact_experience(_store(), created_at="2026-02-01T00:00:00Z"), indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-habit-evidence-summary",
            str(summary_path),
            "navigation.follow_person",
            "--source-store",
            str(STORE),
            "--created-at",
            "2026-02-01T00:00:00Z",
            "--json",
        ],
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["evidence_basis"] == "aggregate"
    assert report["source_verification"] == "raw_verified"
    assert report["metrics"]["repeat_rate"] == 0.8


def test_context_limited_cli_returns_insufficient_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-habit-evidence",
            str(STORE),
            "navigation.follow_person",
            "--context-json",
            '{"zone":"home"}',
            "--created-at",
            "2026-02-01T00:00:00Z",
            "--json",
        ],
    )
    assert main() == 7
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "insufficient"


def test_invalid_context_json_returns_input_error(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-habit-evidence",
            str(STORE),
            "navigation.follow_person",
            "--context-json",
            "[]",
        ],
    )
    assert main() == 2
    assert "ERROR:" in capsys.readouterr().out
