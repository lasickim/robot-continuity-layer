import json
import sys
from pathlib import Path

from rcl.cli_entry import main


ROOT = Path(__file__).resolve().parents[1]
LLM = ROOT / "examples" / "intent-proposer" / "llm-object-release.proposal.json"


def test_inspect_intent_proposal_json_is_explicitly_non_authoritative(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "inspect-intent-proposal", str(LLM), "--json"])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["proposal"]["proposer"]["kind"] == "llm"
    assert result["proposal"]["self_confidence"] == 0.92
    assert result["rcl_confidence_evaluated"] is False
    assert result["profile_mutated"] is False
    assert result["approval_granted"] is False
    assert len(result["proposal_sha256"]) == 64


def test_inspect_intent_proposal_text_surfaces_boundary(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "inspect-intent-proposal", str(LLM)])
    assert main() == 0
    output = capsys.readouterr().out
    assert "Proposer Self-Confidence: 0.920 (NON-NORMATIVE)" in output
    assert "RCL Confidence Evaluated: NO" in output
    assert "Approved: NO" in output
    assert "Profile Mutation: NO" in output


def test_inspect_intent_proposal_rejects_stale_digest(monkeypatch, capsys, tmp_path):
    proposal = json.loads(LLM.read_text(encoding="utf-8"))
    proposal["rationale_summary"] += " modified"
    path = tmp_path / "stale-proposal.json"
    path.write_text(json.dumps(proposal), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["rcl", "inspect-intent-proposal", str(path)])
    assert main() == 2
    assert "proposal_id does not match" in capsys.readouterr().out
