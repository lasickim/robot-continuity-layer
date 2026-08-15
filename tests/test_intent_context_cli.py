import copy
import json
import sys
from pathlib import Path

from rcl import (
    INTENT_CONTEXT_REPORT_METHOD,
    INTENT_CONTEXT_REPORT_VERSION,
    diagnose_intent_context,
    diagnose_intent_context_from_summary,
)
from rcl.cli_router import main
from rcl.experience import compact_experience


ROOT = Path(__file__).resolve().parents[1]
STABLE = ROOT / "examples" / "intent-context" / "stable-object-release.dataset.json"
DEPENDENT = ROOT / "examples" / "intent-context" / "context-dependent-object-release.dataset.json"


def _summary_and_hypothesis(dataset):
    episodes = copy.deepcopy(dataset["episodes"])
    for index, episode in enumerate(episodes, start=1):
        episode["observed_at"] = f"2026-08-15T12:{index:02d}:00Z"
    summary = compact_experience(
        {
            "experience_version": "0.1",
            "store_id": "context-cli-store",
            "episodes": episodes,
        }
    )
    hypothesis = {
        "summary_hypothesis_version": "0.1",
        "dataset_id": dataset["dataset_id"],
        "candidate_action_id": dataset["candidate_action_id"],
        "context_match": dataset["context_match"],
        "outcome": dataset["outcome"],
        "proposed_intent": dataset["proposed_intent"],
    }
    return summary, hypothesis


def test_public_api_exports_context_diagnostics():
    dataset = json.loads(STABLE.read_text(encoding="utf-8"))
    report = diagnose_intent_context(dataset, created_at="2026-08-15T11:00:00Z")
    assert INTENT_CONTEXT_REPORT_VERSION == "0.1"
    assert INTENT_CONTEXT_REPORT_METHOD == "rcl.intent.context_diagnostics.v0.1"
    assert report["diagnostics"]["status"] == "no_material_context_signal"

    summary, hypothesis = _summary_and_hypothesis(dataset)
    aggregate = diagnose_intent_context_from_summary(
        summary,
        hypothesis,
        created_at="2026-08-15T11:00:00Z",
    )
    assert aggregate["diagnostics"]["status"] == "no_material_context_signal"


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


def test_cli_summary_path(monkeypatch, capsys, tmp_path):
    dataset = json.loads(DEPENDENT.read_text(encoding="utf-8"))
    summary, hypothesis = _summary_and_hypothesis(dataset)
    summary_path = tmp_path / "summary.json"
    hypothesis_path = tmp_path / "hypothesis.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    hypothesis_path.write_text(json.dumps(hypothesis), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "diagnose-intent-context-summary",
            str(summary_path),
            str(hypothesis_path),
            "--json",
        ],
    )
    assert main() == 7
    report = json.loads(capsys.readouterr().out)
    assert report["evidence_basis"] == "aggregate"
    assert report["diagnostics"]["status"] == "context_dependency_signal"
