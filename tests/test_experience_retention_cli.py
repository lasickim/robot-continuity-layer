import json
import sys
from pathlib import Path

from rcl.cli_entry import main
from rcl.experience import compact_experience


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "examples" / "experience" / "retention-demo.episodes.json"
AS_OF = "2026-04-01T12:00:00Z"


def _write_summary(tmp_path):
    store = json.loads(STORE.read_text(encoding="utf-8"))
    summary = compact_experience(
        store,
        created_at="2026-03-31T13:00:00Z",
        retained_exemplars=4,
    )
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


def test_cli_evaluate_retention_json(monkeypatch, capsys, tmp_path):
    summary = _write_summary(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-experience-retention",
            str(STORE),
            str(summary),
            "--as-of",
            AS_OF,
            "--json",
        ],
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["binding_verified"] is True
    assert report["counts"]["archive_candidate"] == 7
    assert report["counts"]["prune_candidate"] == 0
    assert report["prune_executed"] is False


def test_cli_record_archive_then_evaluate_prune_candidates(monkeypatch, capsys, tmp_path):
    summary = _write_summary(tmp_path)
    archive = tmp_path / "archive.json"
    argv = [
        "rcl",
        "record-experience-archive",
        str(STORE),
    ]
    for index in range(4, 11):
        argv.extend(["--episode-id", f"table-{index:02d}"])
    argv.extend(
        [
            "--location-ref",
            "archive://cold-store/retention-demo/001",
            "--archived-at",
            "2026-03-31T12:00:00Z",
            "--archived-by",
            "cli-test",
            "--output",
            str(archive),
        ]
    )
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 0
    assert Path(capsys.readouterr().out.strip()) == archive
    record = json.loads(archive.read_text(encoding="utf-8"))
    assert record["archive_executed_by_rcl"] is False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-experience-retention",
            str(STORE),
            str(summary),
            "--archive-record",
            str(archive),
            "--as-of",
            AS_OF,
            "--json",
        ],
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["prune_candidate"] == 6
    assert report["counts"]["archive_candidate"] == 0


def test_cli_human_readable_output_makes_non_destructive_boundary_explicit(monkeypatch, capsys, tmp_path):
    summary = _write_summary(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-experience-retention",
            str(STORE),
            str(summary),
            "--as-of",
            AS_OF,
        ],
    )
    assert main() == 0
    output = capsys.readouterr().out
    assert "Summary Binding: VERIFIED" in output
    assert "Prune Executed: NO" in output
    assert "Archive Executed By RCL: NO" in output


def test_cli_rejects_stale_summary(monkeypatch, capsys, tmp_path):
    summary = _write_summary(tmp_path)
    value = json.loads(summary.read_text(encoding="utf-8"))
    value["source"]["source_digest_sha256"] = "0" * 64
    summary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "evaluate-experience-retention",
            str(STORE),
            str(summary),
            "--as-of",
            AS_OF,
        ],
    )
    assert main() == 2
    assert "source digest does not match" in capsys.readouterr().out
