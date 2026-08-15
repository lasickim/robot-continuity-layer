from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .intent_context_diagnostics import (
    evaluate_aggregate_context_diagnostics,
    evaluate_raw_context_diagnostics,
)
from .intent_discovery import (
    discover_intent_candidate,
    discover_intent_candidate_from_summary,
)
from .profile import validate_schema


INTENT_CONTEXT_REPORT_VERSION = "0.1"
INTENT_CONTEXT_REPORT_METHOD = "rcl.intent.context_diagnostics.v0.1"


def _matches_context(context: dict[str, Any], selector: dict[str, Any]) -> bool:
    return all(context.get(key) == value for key, value in selector.items())


def _report(
    candidate: dict[str, Any],
    diagnostics: dict[str, Any],
    *,
    created_at: str | None,
) -> dict[str, Any]:
    report = {
        "context_diagnostic_version": INTENT_CONTEXT_REPORT_VERSION,
        "method": INTENT_CONTEXT_REPORT_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset_id": candidate["dataset_id"],
        "candidate_id": candidate["candidate_id"],
        "candidate_status": candidate["status"],
        "candidate_confidence": candidate["confidence"],
        "hypothesis": candidate["hypothesis"],
        "evidence_basis": candidate["evidence_basis"],
        "evidence_provenance": candidate["evidence_provenance"],
        "diagnostics": diagnostics,
        "causal_claim": False,
        "disclaimer": (
            "Context Diagnostics v0.1 reports context specificity and possible confound signals from observed associations. "
            "It does not prove confounding, prove causality, reject or approve an Intent Candidate, mutate an RCL profile, "
            "or certify physical safety."
        ),
    }
    validate_schema(report, "intent-context-diagnostic-report")
    return report


def diagnose_intent_context(
    dataset: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a raw-evidence context diagnostic companion to Intent Discovery."""

    candidate = discover_intent_candidate(dataset, policy=policy, created_at=created_at)
    selector = dataset["context_match"]
    context_episodes = [
        episode
        for episode in dataset["episodes"]
        if _matches_context(episode["context"], selector)
    ]
    diagnostics = evaluate_raw_context_diagnostics(dataset, context_episodes)
    return _report(candidate, diagnostics, created_at=created_at)


def diagnose_intent_context_from_summary(
    summary: dict[str, Any],
    hypothesis: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build aggregate context diagnostics without reconstructing pseudo-episodes."""

    candidate = discover_intent_candidate_from_summary(
        summary,
        hypothesis,
        policy=policy,
        created_at=created_at,
    )
    selector = hypothesis["context_match"]
    candidate_action_id = hypothesis["candidate_action_id"]
    outcome_id = hypothesis["outcome"]["outcome_id"]
    matching_groups = [
        group
        for group in summary["groups"]
        if group["action_id"] == candidate_action_id
        and outcome_id in group["outcome_ids"]
        and _matches_context(group["context"], selector)
    ]
    diagnostics = evaluate_aggregate_context_diagnostics(hypothesis, matching_groups)
    return _report(candidate, diagnostics, created_at=created_at)
