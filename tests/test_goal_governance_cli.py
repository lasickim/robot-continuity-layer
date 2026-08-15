import json
import sys
from pathlib import Path

from rcl.cli_entry import main
from rcl.goal_governance import review_goal_proposal


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "goal-governance"
POSITIVE = EXAMPLES / "recipient-ready.proposal.json"
DUPLICATE = EXAMPLES / "duplicate-sitting-goal.proposal.json"
OVERLAP = EXAMPLES / "overlap-sitting-goal.proposal.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_cli_review_ready_json_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "review-goal-proposal", str(POSITIVE), "--json"])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ready_for_review"
    assert report["vocabulary_mutated"] is False


def test_cli_review_advisory_returns_seven(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "review-goal-proposal", str(OVERLAP), "--json"])
    assert main() == 7
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "needs_revision"


def test_cli_review_blocked_returns_eight(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "review-goal-proposal", str(DUPLICATE), "--json"])
    assert main() == 8
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"


def test_cli_decision_writes_immutable_record(monkeypatch, capsys, tmp_path):
    proposal = _load(POSITIVE)
    review = review_goal_proposal(proposal, created_at="2026-08-15T15:00:00Z")
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    output = tmp_path / "decision.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "decide-goal-proposal",
            str(POSITIVE),
            str(review_path),
            "--decision",
            "approved",
            "--reviewed-at",
            "2026-08-15T15:10:00Z",
            "--reviewed-by",
            "reviewer@example.org",
            "--reason",
            "Portable goal accepted for an explicit vocabulary change proposal.",
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    assert Path(capsys.readouterr().out.strip()) == output
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["decision"] == "approved"
    assert record["vocabulary_mutated"] is False
    assert record["next_action"] == "submit_explicit_vocabulary_change"


def test_cli_entry_still_delegates_existing_rcl_commands(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "capabilities", "list", "--json"])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["registry_version"] == "0.1"
    assert payload["capabilities"]
