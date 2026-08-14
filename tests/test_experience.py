import copy
import json
import sys
from pathlib import Path

import pytest

from rcl.cli_router import main as routed_main
from rcl.experience import EXPERIENCE_COMPACTION_METHOD, compact_experience
from rcl.profile import RCLValidationError, validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fixture() -> dict:
    return json.loads(
        (_root() / "examples" / "experience" / "mixed-robot-life.episodes.json").read_text(encoding="utf-8")
    )


def _group(summary: dict, action_id: str) -> dict:
    return next(item for item in summary["groups"] if item["action_id"] == action_id)


def test_reference_experience_compacts_into_semantic_groups():
    store = _fixture()
    validate_schema(store, "experience-episode-set")

    summary = compact_experience(store, created_at="2026-08-14T08:10:00Z")
    validate_schema(summary, "experience-summary")

    assert summary["summary_version"] == "0.1"
    assert summary["method"] == EXPERIENCE_COMPACTION_METHOD
    assert summary["destructive"] is False
    assert summary["source"]["episode_count"] == 10
    assert summary["group_count"] == 2


def test_numeric_and_binary_outcomes_are_aggregated_without_behavior_hardcoding():
    summary = compact_experience(_fixture(), created_at="2026-08-14T08:10:00Z")

    release = _group(summary, "interaction.post_release_hold")
    assert release["episode_count"] == 6
    assert release["action_present_count"] == 4
    assert release["action_absent_count"] == 2
    stability = release["outcomes"]["object_stability"]
    assert stability["type"] == "numeric"
    assert stability["count"] == 6
    assert stability["mean"] == pytest.approx(0.84)
    assert stability["min"] == pytest.approx(0.62)
    assert stability["max"] == pytest.approx(0.96)
    assert stability["sample_std"] is not None

    settled = release["outcomes"]["object_settled"]
    assert settled == {
        "type": "binary",
        "count": 6,
        "true_count": 5,
        "false_count": 1,
        "true_rate": 0.833333,
    }

    dock = _group(summary, "navigation.pre_dock_alignment_pause")
    assert dock["episode_count"] == 4
    assert dock["outcomes"]["docking_success"]["true_rate"] == 0.75


def test_compaction_is_deterministic_and_non_mutating():
    store = _fixture()
    original = copy.deepcopy(store)

    first = compact_experience(store, created_at="2026-08-14T08:10:00Z")
    second = compact_experience(store, created_at="2026-08-14T08:10:00Z")

    assert first == second
    assert store == original
    assert first["source"]["source_digest_sha256"] == second["source"]["source_digest_sha256"]
    assert first["summary_id"] == second["summary_id"]


def test_summary_identity_does_not_depend_on_wall_clock_creation_time():
    store = _fixture()
    first = compact_experience(store, created_at="2026-08-14T08:10:00Z")
    second = compact_experience(store, created_at="2026-08-15T08:10:00Z")

    assert first["created_at"] != second["created_at"]
    assert first["summary_id"] == second["summary_id"]
    assert first["source"]["source_digest_sha256"] == second["source"]["source_digest_sha256"]


def test_default_exemplars_keep_early_and_late_longitudinal_anchors():
    summary = compact_experience(_fixture(), created_at="2026-08-14T08:10:00Z")
    release = _group(summary, "interaction.post_release_hold")

    assert release["provenance"]["retained_exemplar_episode_ids"] == [
        "release-001",
        "release-002",
        "release-005",
        "release-006",
    ]
    assert release["provenance"]["source_episode_count"] == 6
    assert len(release["provenance"]["source_episode_id_digest_sha256"]) == 64


def test_context_change_creates_a_separate_group_instead_of_silent_averaging():
    store = _fixture()
    store["episodes"][0]["context"]["surface"] = "shelf"

    summary = compact_experience(store, created_at="2026-08-14T08:10:00Z")

    assert summary["group_count"] == 3
    release_groups = [
        group for group in summary["groups"]
        if group["action_id"] == "interaction.post_release_hold"
    ]
    assert {group["context"]["surface"] for group in release_groups} == {"table", "shelf"}


def test_mixed_outcome_types_in_one_semantic_group_are_rejected():
    store = _fixture()
    store["episodes"][1]["outcomes"]["object_stability"] = True

    with pytest.raises(RCLValidationError, match="mixes types"):
        compact_experience(store)


def test_duplicate_episode_ids_and_negative_exemplar_count_are_rejected():
    store = _fixture()
    store["episodes"][1]["episode_id"] = store["episodes"][0]["episode_id"]
    with pytest.raises(RCLValidationError, match="Duplicate experience episode_id"):
        compact_experience(store)

    with pytest.raises(RCLValidationError, match="retained_exemplars"):
        compact_experience(_fixture(), retained_exemplars=-1)


def test_zero_exemplars_is_valid_and_does_not_delete_source_evidence():
    store = _fixture()
    original_count = len(store["episodes"])
    summary = compact_experience(store, retained_exemplars=0, created_at="2026-08-14T08:10:00Z")

    assert all(not group["provenance"]["retained_exemplar_episode_ids"] for group in summary["groups"])
    assert summary["destructive"] is False
    assert len(store["episodes"]) == original_count


def test_public_and_runtime_experience_schemas_match():
    root = _root()
    for name in ("experience-episode-set.schema.json", "experience-summary.schema.json"):
        runtime = json.loads((root / "rcl" / "schemas" / name).read_text(encoding="utf-8"))
        public = json.loads((root / "spec" / "schemas" / name).read_text(encoding="utf-8"))
        assert public == runtime


def test_compact_experience_cli_json(monkeypatch, capsys):
    source = _root() / "examples" / "experience" / "mixed-robot-life.episodes.json"
    monkeypatch.setattr(sys, "argv", ["rcl", "compact-experience", str(source), "--json"])

    assert routed_main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["summary_version"] == "0.1"
    assert summary["group_count"] == 2
    assert summary["destructive"] is False
