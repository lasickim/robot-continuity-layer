import copy
import json
from pathlib import Path

from rcl.experience import compact_experience
from rcl.intent_context_report import (
    diagnose_intent_context,
    diagnose_intent_context_from_summary,
)
from rcl.intent_discovery import discover_intent_candidate
from rcl.profile import validate_schema


ROOT = Path(__file__).resolve().parents[1]
STABLE = ROOT / "examples" / "intent-context" / "stable-object-release.dataset.json"
DEPENDENT = ROOT / "examples" / "intent-context" / "context-dependent-object-release.dataset.json"
LEGACY = ROOT / "examples" / "intent-discovery" / "object-release-stability.dataset.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _hypothesis(dataset):
    return {
        "summary_hypothesis_version": "0.1",
        "dataset_id": dataset["dataset_id"],
        "candidate_action_id": dataset["candidate_action_id"],
        "context_match": dataset["context_match"],
        "outcome": dataset["outcome"],
        "proposed_intent": dataset["proposed_intent"],
    }


def _summary(dataset):
    episodes = copy.deepcopy(dataset["episodes"])
    for index, episode in enumerate(episodes, start=1):
        episode["observed_at"] = f"2026-08-15T11:{index:02d}:00Z"
    store = {
        "experience_version": "0.1",
        "store_id": f"store-{dataset['dataset_id']}",
        "episodes": episodes,
    }
    return compact_experience(store)


def test_context_stable_raw_evidence_has_no_material_signal():
    report = diagnose_intent_context(_load(STABLE), created_at="2026-08-15T11:00:00Z")

    validate_schema(report, "intent-context-diagnostic-report")
    assert report["candidate_status"] == "candidate"
    diagnostic = report["diagnostics"]
    assert diagnostic["status"] == "no_material_context_signal"
    assert diagnostic["review_required"] is False
    assert diagnostic["evaluated_fields"] == ["surface"]
    field = diagnostic["fields"][0]
    assert field["supported_value_count"] == 2
    assert field["action_prevalence_signal"] is False
    assert field["effect_heterogeneity_signal"] is False
    assert {item["effect_direction"] for item in field["strata"]} == {"beneficial"}


def test_context_dependent_effect_is_reported_without_rejecting_candidate():
    dataset = _load(DEPENDENT)
    candidate = discover_intent_candidate(dataset, created_at="2026-08-15T11:00:00Z")
    report = diagnose_intent_context(dataset, created_at="2026-08-15T11:00:00Z")

    assert candidate["status"] == "candidate"
    assert report["candidate_status"] == candidate["status"]
    diagnostic = report["diagnostics"]
    assert diagnostic["status"] == "context_dependency_signal"
    assert diagnostic["review_required"] is True
    assert "surface:effect_heterogeneity" in diagnostic["warnings"]
    field = diagnostic["fields"][0]
    assert field["effect_heterogeneity_signal"] is True
    assert {item["effect_direction"] for item in field["strata"]} == {
        "beneficial",
        "neutral_or_harmful",
    }
    assert report["causal_claim"] is False
    assert diagnostic["causal_claim"] is False


def test_action_prevalence_imbalance_is_reported_separately():
    dataset = _load(STABLE)
    for episode in dataset["episodes"]:
        if episode["context"]["surface"] == "table":
            episode["action"]["performed"] = True
    report = diagnose_intent_context(dataset, created_at="2026-08-15T11:00:00Z")

    diagnostic = report["diagnostics"]
    assert diagnostic["status"] == "context_dependency_signal"
    field = diagnostic["fields"][0]
    assert field["action_repeat_rate_spread"] == 0.5
    assert field["action_prevalence_signal"] is True
    assert "surface:action_prevalence_imbalance" in diagnostic["warnings"]


def test_existing_single_surface_fixture_reports_no_residual_context_fields():
    report = diagnose_intent_context(_load(LEGACY), created_at="2026-08-15T11:00:00Z")

    diagnostic = report["diagnostics"]
    assert diagnostic["status"] == "no_residual_context_fields"
    assert diagnostic["evaluated_fields"] == []
    assert diagnostic["fields"] == []
    assert diagnostic["review_required"] is False


def test_insufficient_context_coverage_is_explicit_without_false_imbalance_signal():
    dataset = _load(STABLE)
    tray_present = [
        episode for episode in dataset["episodes"]
        if episode["context"]["surface"] == "tray" and episode["action"]["performed"]
    ]
    tray_absent = [
        episode for episode in dataset["episodes"]
        if episode["context"]["surface"] == "tray" and not episode["action"]["performed"]
    ]
    for index, (present, absent) in enumerate(zip(tray_present, tray_absent), start=1):
        value = f"tray-{index}"
        present["context"]["surface"] = value
        absent["context"]["surface"] = value

    report = diagnose_intent_context(dataset, created_at="2026-08-15T11:00:00Z")

    diagnostic = report["diagnostics"]
    assert diagnostic["status"] == "insufficient_context_coverage"
    assert diagnostic["review_required"] is True
    field = diagnostic["fields"][0]
    assert field["action_prevalence_signal"] is False
    assert field["supported_value_count"] == 1
    assert "surface:insufficient_context_coverage" in diagnostic["warnings"]


def test_raw_and_aggregate_context_diagnostics_match_for_equivalent_evidence():
    dataset = _load(STABLE)
    raw = diagnose_intent_context(dataset, created_at="2026-08-15T11:00:00Z")
    aggregate = diagnose_intent_context_from_summary(
        _summary(dataset),
        _hypothesis(dataset),
        created_at="2026-08-15T11:00:00Z",
    )

    assert raw["candidate_status"] == aggregate["candidate_status"] == "candidate"
    raw_diag = copy.deepcopy(raw["diagnostics"])
    aggregate_diag = copy.deepcopy(aggregate["diagnostics"])
    raw_diag.pop("evidence_basis")
    aggregate_diag.pop("evidence_basis")
    assert raw_diag == aggregate_diag
    assert aggregate["evidence_basis"] == "aggregate"


def test_context_dependent_signal_survives_aggregate_compaction():
    dataset = _load(DEPENDENT)
    report = diagnose_intent_context_from_summary(
        _summary(dataset),
        _hypothesis(dataset),
        created_at="2026-08-15T11:00:00Z",
    )

    assert report["candidate_status"] == "candidate"
    assert report["diagnostics"]["status"] == "context_dependency_signal"
    assert "surface:effect_heterogeneity" in report["diagnostics"]["warnings"]


def test_runtime_and_public_context_diagnostic_schemas_match():
    runtime = json.loads(
        (ROOT / "rcl" / "schemas" / "intent-context-diagnostic-report.schema.json").read_text(encoding="utf-8")
    )
    public = json.loads(
        (ROOT / "spec" / "schemas" / "intent-context-diagnostic-report.schema.json").read_text(encoding="utf-8")
    )
    assert runtime == public
