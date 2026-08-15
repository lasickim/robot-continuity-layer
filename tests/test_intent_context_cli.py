import json
import sys
from pathlib import Path

from rcl import (
    INTENT_CONTEXT_REPORT_METHOD,
    INTENT_CONTEXT_REPORT_VERSION,
    diagnose_intent_context,
)
from rcl.cli_router import main


ROOT = Path(__file__).resolve().parents[1]
STABLE = ROOT / "examples" / "intent-context" / "stable-object-release.dataset.json"
DEPENDENT = ROOT / "examples" / "intent-context" / "context-dependent-object-release.dataset.json"


def test_public_api_exports_context_diagnostics():
    dataset = json.loads(STABLE.read_text(encoding="utf-8"))
    report = diagnose_intent_context(dataset, created_at="2026-08-15T11:00:00Z")
    assert INTENT_CONTEXT_REPORT_VERSION == "0.1"
    assert INTENT_CONTEXT_REPORT_METHOD == "rcl.intent.context_diagnostics.v0.1"
    assert report["diagnostics"]["status"] == "no_material_context_signal"


def test_cli_raw_json_stable_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["rcl", "diagnose-intent-context", str(STABLE), "--json"],
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["diagnostics"]["review_required"] is False


def test_cli_raw_context_dependency_returns_review_code(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["rcl", "diagnose-intent-context", str(DEPENDENT), "--json"],
    )
    assert main() == 7
    report = json.loads(capsys.readouterr().out)
    assert report["candidate_status"] == "candidate"
    assert report["diagnostics"]["status"] == "context_dependency_signal"
    assert report["diagnostics"]["review_required"] is True


def test_cli_output_file(monkeypatch, capsys, tmp_path):
    output = tmp_path / "context-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["rcl", "diagnose-intent-context", str(STABLE), "--output", str(output)],
    )
    assert main() == 0
    assert Path(capsys.readouterr().out.strip()) == output
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["method"] == "rcl.intent.context_diagnostics.v0.1"
