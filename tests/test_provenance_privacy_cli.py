import json
import sys
from pathlib import Path

from rcl.cli_entry import main


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "examples" / "governance" / "public-artifact.json"
PRIVATE = ROOT / "examples" / "governance" / "private-source.json"


def test_record_and_evaluate_public_artifact_cli(monkeypatch, capsys, tmp_path):
    record_path = tmp_path / "public.provenance.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "record-artifact-provenance",
            str(PUBLIC),
            "--artifact-id",
            "public-note-cli",
            "--artifact-type",
            "documentation.note",
            "--created-at",
            "2026-08-16T00:00:00Z",
            "--created-by",
            "maintainer@example.org",
            "--origin-kind",
            "operator",
            "--classification",
            "public",
            "--sharing-scope",
            "public",
            "--evidence-ref-propagation",
            "public",
            "--output",
            str(record_path),
        ],
    )
    assert main() == 0
    capsys.readouterr()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["privacy"]["classification"] == "public"
    assert record["content_privacy_inferred"] is False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-artifact-governance",
            str(PUBLIC),
            str(record_path),
            "--operation",
            "share_public",
            "--include-evidence-refs",
            "--created-at",
            "2026-08-16T00:05:00Z",
            "--json",
        ],
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "allowed"
    assert report["share_executed"] is False


def test_private_public_share_cli_returns_blocked_exit(monkeypatch, capsys, tmp_path):
    record_path = tmp_path / "private.provenance.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "record-artifact-provenance",
            str(PRIVATE),
            "--artifact-id",
            "private-source-cli",
            "--artifact-type",
            "experience.semantic_excerpt",
            "--created-at",
            "2026-08-16T00:00:00Z",
            "--created-by",
            "robot-runtime",
            "--origin-kind",
            "sensor",
            "--classification",
            "private",
            "--sharing-scope",
            "approved_recipients",
            "--output",
            str(record_path),
        ],
    )
    assert main() == 0
    capsys.readouterr()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-artifact-governance",
            str(PRIVATE),
            str(record_path),
            "--operation",
            "share_public",
            "--created-at",
            "2026-08-16T00:05:00Z",
            "--json",
        ],
    )
    assert main() == 7
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"


def test_invalid_copy_request_returns_input_error(monkeypatch, capsys, tmp_path):
    record_path = tmp_path / "public.provenance.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "record-artifact-provenance",
            str(PUBLIC),
            "--artifact-id",
            "public-note-cli",
            "--artifact-type",
            "documentation.note",
            "--created-at",
            "2026-08-16T00:00:00Z",
            "--created-by",
            "maintainer@example.org",
            "--origin-kind",
            "operator",
            "--classification",
            "public",
            "--sharing-scope",
            "public",
            "--output",
            str(record_path),
        ],
    )
    assert main() == 0
    capsys.readouterr()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-artifact-governance",
            str(PUBLIC),
            str(record_path),
            "--operation",
            "share_public",
            "--copy-evidence-content",
        ],
    )
    assert main() == 2
    assert "ERROR:" in capsys.readouterr().out
