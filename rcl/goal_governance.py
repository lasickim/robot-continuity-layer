from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from .intent import load_intent_vocabulary
from .profile import RCLValidationError, validate_schema


GOAL_GOVERNANCE_VERSION = "0.1"
GOAL_GOVERNANCE_REVIEW_METHOD = "rcl.intent.goal_vocabulary_review.v0.1"
GOAL_GOVERNANCE_DECISION_METHOD = "rcl.intent.goal_vocabulary_decision.v0.1"

_SEGMENT = r"[a-z][a-z0-9_]*"
_OWNER = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_STANDARD_GOAL_RE = re.compile(rf"^(?P<namespace>{_SEGMENT})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")
_EXTENSION_GOAL_RE = re.compile(rf"^x\.(?P<owner>{_OWNER})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")
_SEMANTIC_NAME_RE = re.compile(rf"^{_SEGMENT}(?:\.{_SEGMENT})+$")
_TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "to", "when", "with",
    "robot", "should", "must", "intended", "portable", "goal", "state", "activity",
}

# These terms do not make a proposal wrong. They are review signals that a shared
# semantic goal may have accidentally captured one body's implementation recipe.
_HARDWARE_TERMS = {
    "camera", "lidar", "tof", "gpio", "uart", "i2c", "ros", "ros2", "servo",
    "motor", "actuator", "joint", "wheel", "gripper", "manipulator", "encoder",
    "depth_camera", "rgb_camera", "jetson", "raspberry", "stm32",
}

_VALID_FAILURE_ACTIONS = {"block", "retry", "request_help", "abort", "degrade_safely"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if parsed.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return parsed


def _proposal_material(proposal: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in proposal.items() if key != "proposal_id"}


def expected_goal_proposal_id(proposal: dict[str, Any]) -> str:
    digest = _sha256_json(_proposal_material(proposal))[:16]
    return f"goal-proposal-{digest}"


def goal_proposal_sha256(proposal: dict[str, Any]) -> str:
    return _sha256_json(proposal)


def _tokens(*values: str) -> set[str]:
    result: set[str] = set()
    for value in values:
        for token in _TOKEN_RE.findall(value.lower().replace(".", " ")):
            if token not in _STOPWORDS:
                result.add(token)
    return result


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _specificity_hits(goal: dict[str, Any]) -> list[dict[str, str]]:
    fields: list[tuple[str, str]] = [
        ("goal_id", goal["goal_id"]),
        ("summary", goal["summary"]),
        ("semantics", goal["semantics"]),
    ]
    fields.extend(("triggers", item) for item in goal["triggers"])
    fields.extend(("success_conditions", item) for item in goal["success_conditions"])

    hits: list[dict[str, str]] = []
    for field, value in fields:
        normalized = value.lower().replace("-", "_").replace(".", " ")
        words = set(_TOKEN_RE.findall(normalized))
        for term in sorted(_HARDWARE_TERMS & words):
            hits.append({"field": field, "term": term})
    return hits


def _check(
    check_id: str,
    *,
    passed: bool,
    severity: str,
    summary: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": bool(passed),
        "severity": severity,
        "summary": summary,
        "details": details or {},
    }


def review_goal_proposal(
    proposal: dict[str, Any],
    *,
    vocabulary: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Review a proposal for shared RCL standard-goal vocabulary inclusion.

    The review is deterministic and advisory except for structural/ID collision
    blockers. It never mutates the bundled vocabulary.
    """

    validate_schema(proposal, "goal-vocabulary-proposal")
    _parse_datetime(proposal["created_at"], label="proposal.created_at")

    expected_id = expected_goal_proposal_id(proposal)
    id_integrity = proposal["proposal_id"] == expected_id
    goal = proposal["proposed_goal"]
    goal_id = goal["goal_id"]

    effective_vocabulary = vocabulary or load_intent_vocabulary()
    registered = list(effective_vocabulary["goals"])
    registered_by_id = {item["goal_id"]: item for item in registered}

    standard_syntax = _STANDARD_GOAL_RE.fullmatch(goal_id) is not None and not goal_id.startswith("x.")
    exact_collision = goal_id in registered_by_id

    source_extensions = proposal.get("source_extension_goal_ids", [])
    source_extensions_valid = all(_EXTENSION_GOAL_RE.fullmatch(item) is not None for item in source_extensions)

    proposal_tokens = _tokens(goal_id, goal["summary"], goal["semantics"])
    overlap_candidates: list[dict[str, Any]] = []
    for existing in registered:
        existing_tokens = _tokens(existing["goal_id"], existing["summary"], existing["semantics"])
        score = round(_jaccard(proposal_tokens, existing_tokens), 6)
        if score > 0:
            overlap_candidates.append({"goal_id": existing["goal_id"], "token_overlap": score})
    overlap_candidates.sort(key=lambda item: (-item["token_overlap"], item["goal_id"]))
    top_overlap = overlap_candidates[0]["token_overlap"] if overlap_candidates else 0.0
    semantic_overlap_signal = top_overlap >= 0.35

    specificity_hits = _specificity_hits(goal)

    trigger_quality = all(_SEMANTIC_NAME_RE.fullmatch(item) is not None for item in goal["triggers"])
    success_quality = all(
        _SEMANTIC_NAME_RE.fullmatch(item) is not None and item.startswith("state.")
        for item in goal["success_conditions"]
    )
    failure_actions_valid = set(goal["allowed_failure_actions"]) <= _VALID_FAILURE_ACTIONS

    checks = [
        _check(
            "proposal_id_integrity",
            passed=id_integrity,
            severity="blocker",
            summary="Proposal ID must match the deterministic proposal material digest.",
            details={"expected": expected_id, "actual": proposal["proposal_id"]},
        ),
        _check(
            "standard_goal_id_syntax",
            passed=standard_syntax,
            severity="blocker",
            summary="Shared vocabulary proposals must use standard semantic goal IDs, not x.<owner> extensions.",
            details={"goal_id": goal_id},
        ),
        _check(
            "exact_goal_id_collision",
            passed=not exact_collision,
            severity="blocker",
            summary="A proposed standard goal ID must not already be registered.",
            details={"goal_id": goal_id, "collision": exact_collision},
        ),
        _check(
            "source_extension_provenance",
            passed=source_extensions_valid,
            severity="blocker",
            summary="Source extension goal IDs, when supplied, must use x.<owner>.<semantic_path>.",
            details={"source_extension_goal_ids": source_extensions},
        ),
        _check(
            "semantic_overlap",
            passed=not semantic_overlap_signal,
            severity="advisory",
            summary="Substantial vocabulary overlap should be reviewed for duplicate or refinable semantics.",
            details={"threshold": 0.35, "top_overlap": top_overlap, "candidates": overlap_candidates[:5]},
        ),
        _check(
            "body_neutrality",
            passed=not specificity_hits,
            severity="advisory",
            summary="Shared goals should describe portable purpose rather than one body's hardware recipe.",
            details={"specificity_hits": specificity_hits},
        ),
        _check(
            "trigger_semantics",
            passed=trigger_quality,
            severity="advisory",
            summary="Triggers should use semantic dotted names rather than implementation-specific identifiers.",
            details={"triggers": goal["triggers"]},
        ),
        _check(
            "success_condition_semantics",
            passed=success_quality,
            severity="advisory",
            summary="Success conditions should be semantic state.* identifiers.",
            details={"success_conditions": goal["success_conditions"]},
        ),
        _check(
            "failure_action_vocabulary",
            passed=failure_actions_valid,
            severity="blocker",
            summary="Failure actions must use the existing Behavior Intent failure-action vocabulary.",
            details={"allowed_failure_actions": goal["allowed_failure_actions"]},
        ),
    ]

    blockers = [item["check_id"] for item in checks if item["severity"] == "blocker" and not item["passed"]]
    advisories = [item["check_id"] for item in checks if item["severity"] == "advisory" and not item["passed"]]

    if blockers:
        status = "blocked"
        eligible_for_approval = False
        recommended_decision = "needs_revision"
    elif advisories:
        status = "needs_revision"
        eligible_for_approval = True
        recommended_decision = "needs_revision"
    else:
        status = "ready_for_review"
        eligible_for_approval = True
        recommended_decision = "approved"

    report = {
        "goal_governance_review_version": GOAL_GOVERNANCE_VERSION,
        "method": GOAL_GOVERNANCE_REVIEW_METHOD,
        "created_at": created_at or proposal["created_at"],
        "proposal_id": proposal["proposal_id"],
        "proposal_sha256": goal_proposal_sha256(proposal),
        "proposed_goal_id": goal_id,
        "vocabulary": {
            "vocabulary_id": effective_vocabulary["vocabulary_id"],
            "vocabulary_version": effective_vocabulary["vocabulary_version"],
            "vocabulary_sha256": _sha256_json(effective_vocabulary),
        },
        "status": status,
        "eligible_for_approval": eligible_for_approval,
        "recommended_decision": recommended_decision,
        "blockers": blockers,
        "advisories": advisories,
        "checks": checks,
        "overlap_candidates": overlap_candidates[:5],
        "specificity_hits": specificity_hits,
        "vocabulary_mutated": False,
        "disclaimer": (
            "Goal Vocabulary Governance v0.1 provides deterministic review assistance for the draft shared RCL vocabulary. "
            "It does not prove universal semantic correctness, infer robot Intent, mutate the bundled vocabulary, or confer standards-body authority."
        ),
    }
    validate_schema(report, "goal-vocabulary-review-report")
    return report


def _decision_id(material: dict[str, Any]) -> str:
    return f"goal-decision-{_sha256_json(material)[:16]}"


def record_goal_proposal_decision(
    proposal: dict[str, Any],
    review_report: dict[str, Any],
    *,
    decision: str,
    reviewed_at: str,
    reviewed_by: str,
    reason: str,
) -> dict[str, Any]:
    """Create an immutable decision record bound to an exact proposal/review pair."""

    validate_schema(proposal, "goal-vocabulary-proposal")
    validate_schema(review_report, "goal-vocabulary-review-report")
    _parse_datetime(reviewed_at, label="reviewed_at")

    if decision not in {"approved", "rejected", "needs_revision"}:
        raise RCLValidationError(f"Unsupported goal-governance decision: {decision}")
    if not reviewed_by.strip():
        raise RCLValidationError("reviewed_by must be non-empty")
    if not reason.strip():
        raise RCLValidationError("reason must be non-empty")

    proposal_sha = goal_proposal_sha256(proposal)
    if review_report["proposal_id"] != proposal["proposal_id"]:
        raise RCLValidationError("Review report proposal_id does not match proposal")
    if review_report["proposal_sha256"] != proposal_sha:
        raise RCLValidationError("Review report is stale: proposal SHA-256 no longer matches")
    if decision == "approved" and not review_report["eligible_for_approval"]:
        raise RCLValidationError("Blocked goal proposal cannot be approved")

    review_sha = _sha256_json(review_report)
    material = {
        "proposal_id": proposal["proposal_id"],
        "proposal_sha256": proposal_sha,
        "review_report_sha256": review_sha,
        "decision": decision,
        "reviewed_at": reviewed_at,
        "reviewed_by": reviewed_by,
        "reason": reason,
    }
    next_action = {
        "approved": "submit_explicit_vocabulary_change",
        "rejected": "archive_rejected_proposal",
        "needs_revision": "revise_and_resubmit_proposal",
    }[decision]
    record = {
        "goal_governance_decision_version": GOAL_GOVERNANCE_VERSION,
        "method": GOAL_GOVERNANCE_DECISION_METHOD,
        "decision_id": _decision_id(material),
        "proposal_id": proposal["proposal_id"],
        "proposal_sha256": proposal_sha,
        "review_report_sha256": review_sha,
        "review_status": review_report["status"],
        "decision": decision,
        "reviewed_at": reviewed_at,
        "reviewed_by": reviewed_by,
        "reason": reason,
        "vocabulary_mutated": False,
        "next_action": next_action,
        "disclaimer": (
            "This record captures an explicit review decision for the exact proposal digest. "
            "Approval does not itself modify the bundled RCL vocabulary; vocabulary changes remain explicit repository/spec changes."
        ),
    }
    validate_schema(record, "goal-vocabulary-decision-record")
    return record
