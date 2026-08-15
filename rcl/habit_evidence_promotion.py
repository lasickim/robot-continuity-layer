from __future__ import annotations

from typing import Any, Iterable

from .habit_policy import evaluate_habit_promotion_candidates
from .profile import RCLProfile, RCLValidationError, validate_schema


def evaluate_habit_promotion_with_formation_evidence(
    profile: RCLProfile,
    session_report: dict[str, Any],
    *,
    formation_evidence_reports: Iterable[dict[str, Any]] = (),
    policy: dict[str, Any] | None = None,
    as_of: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Opt in to Habit Promotion with additional raw/aggregate formation evidence.

    Existing Habit Promotion semantics remain unchanged unless a matching Habit
    Evidence Report is explicitly supplied. Aggregate reports remain aggregate;
    this helper never creates history events or pseudo-episodes.
    """

    evidence_by_behavior: dict[str, dict[str, Any]] = {}
    for evidence in formation_evidence_reports:
        validate_schema(evidence, "habit-evidence-report")
        behavior_id = evidence["behavior_id"]
        if behavior_id in evidence_by_behavior:
            raise RCLValidationError(
                f"Duplicate Habit Evidence Report for behavior_id: {behavior_id}"
            )
        evidence_by_behavior[behavior_id] = evidence

    report = evaluate_habit_promotion_candidates(
        profile,
        session_report,
        policy=policy,
        as_of=as_of,
        created_at=created_at,
    )

    for decision in report["decisions"]:
        if decision["decision"] == "terminal":
            continue
        evidence = evidence_by_behavior.get(decision["behavior_id"])
        if evidence is None:
            continue

        metrics = evidence["metrics"]
        passed = bool(evidence["supports_habit_review"])
        decision["gates"].append(
            {
                "gate": "habit_formation_evidence",
                "passed": passed,
                "actual": {
                    "status": evidence["status"],
                    "evidence_basis": evidence["evidence_basis"],
                    "source_verification": evidence["source_verification"],
                    "episode_count": metrics["episode_count"],
                    "action_present_count": metrics["action_present_count"],
                    "repeat_rate": metrics["repeat_rate"],
                    "observation_span_days": metrics["observation_span_days"],
                    "pseudo_episodes_created": evidence["pseudo_episodes_created"],
                },
                "required": {"status": "sufficient"},
                "reason": (
                    "When explicitly supplied, Habit formation evidence must satisfy its own versioned policy. "
                    "Aggregate evidence remains aggregate and never substitutes synthetic history events."
                ),
            }
        )
        eligible = all(item["passed"] for item in decision["gates"])
        decision["eligible"] = eligible
        decision["decision"] = "candidate" if eligible else "blocked"

    nonterminal = [item for item in report["decisions"] if item["decision"] != "terminal"]
    report["eligible_count"] = sum(1 for item in nonterminal if item["eligible"])
    report["blocked_count"] = sum(1 for item in nonterminal if not item["eligible"])
    report["disclaimer"] += (
        " Optional Habit Evidence reports, when supplied, are supporting formation evidence only; "
        "they do not create habit history events or autonomously approve lifecycle changes."
    )
    validate_schema(report, "habit-promotion-report")
    return report
