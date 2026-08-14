from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files
from math import ceil
from typing import Any

from .intent import validate_behavior_intent_metadata
from .profile import RCLValidationError, validate_schema


INTENT_DISCOVERY_VERSION = "0.1"
INTENT_DISCOVERY_METHOD = "rcl.intent.discovery.context_action_outcome.v0.1"
DEFAULT_DISCOVERY_POLICY_RESOURCE = "intent-discovery-policy-v0.1.json"


def load_default_intent_discovery_policy() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", DEFAULT_DISCOVERY_POLICY_RESOURCE)
    policy = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(policy, "intent-discovery-policy")
    return policy


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _candidate_id(hypothesis: dict[str, Any]) -> str:
    material = {
        "dataset_id": hypothesis["dataset_id"],
        "candidate_action_id": hypothesis["candidate_action_id"],
        "context_match": hypothesis["context_match"],
        "outcome_id": hypothesis["outcome"]["outcome_id"],
        "goal_id": hypothesis["proposed_intent"]["goal_id"],
    }
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()[:16]
    return f"intent-candidate-{digest}"


def _matches_context(context: dict[str, Any], selector: dict[str, Any]) -> bool:
    return all(context.get(key) == value for key, value in selector.items())


def _outcome_value(value: Any, outcome_type: str, *, episode_id: str, outcome_id: str) -> float:
    if outcome_type == "binary":
        if not isinstance(value, bool):
            raise RCLValidationError(
                f"{episode_id}: binary outcome {outcome_id} must be true/false"
            )
        return 1.0 if value else 0.0

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RCLValidationError(
            f"{episode_id}: numeric outcome {outcome_id} must be a number"
        )
    return float(value)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _gate(
    name: str,
    *,
    actual: Any,
    required: Any,
    passed: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "actual": actual,
        "required": required,
        "reason": reason,
    }


def _validate_hypothesis(hypothesis: dict[str, Any]) -> None:
    # Reuse the same goal/capability vocabulary checks as a real behavior intent
    # without mutating or constructing an RCL profile.
    synthetic = {
        "behaviors": [
            {
                "behavior_id": "x.rcl.intent_discovery_candidate",
                "parameters": {},
                "preservation": {"priority": "optional", "mode": "semantic"},
                "intent": hypothesis["proposed_intent"],
            }
        ]
    }
    validate_behavior_intent_metadata(synthetic)


def _validate_dataset_cross_fields(dataset: dict[str, Any]) -> None:
    episode_ids: set[str] = set()
    candidate_action_id = dataset["candidate_action_id"]
    outcome_id = dataset["outcome"]["outcome_id"]
    outcome_type = dataset["outcome"]["type"]

    for episode in dataset["episodes"]:
        episode_id = episode["episode_id"]
        if episode_id in episode_ids:
            raise RCLValidationError(f"Duplicate intent-discovery episode_id: {episode_id}")
        episode_ids.add(episode_id)

        action_id = episode["action"]["action_id"]
        if action_id != candidate_action_id:
            raise RCLValidationError(
                f"{episode_id}: action_id {action_id!r} does not match candidate_action_id {candidate_action_id!r}"
            )

        if _matches_context(episode["context"], dataset["context_match"]):
            if outcome_id not in episode["outcomes"]:
                raise RCLValidationError(
                    f"{episode_id}: matching-context episode is missing outcome {outcome_id!r}"
                )
            _outcome_value(
                episode["outcomes"][outcome_id],
                outcome_type,
                episode_id=episode_id,
                outcome_id=outcome_id,
            )

    _validate_hypothesis(dataset)


def _validate_summary_cross_fields(summary: dict[str, Any]) -> None:
    if summary["group_count"] != len(summary["groups"]):
        raise RCLValidationError("Experience Summary group_count does not match groups length")

    seen_group_ids: set[str] = set()
    source_count = 0
    for group in summary["groups"]:
        group_id = group["group_id"]
        if group_id in seen_group_ids:
            raise RCLValidationError(f"Duplicate Experience Summary group_id: {group_id}")
        seen_group_ids.add(group_id)

        if group["action_present_count"] + group["action_absent_count"] != group["episode_count"]:
            raise RCLValidationError(
                f"{group_id}: action-present/absent counts do not sum to episode_count"
            )
        if group["provenance"]["source_episode_count"] != group["episode_count"]:
            raise RCLValidationError(
                f"{group_id}: provenance source_episode_count does not match episode_count"
            )
        source_count += group["episode_count"]

        strata = group.get("action_strata")
        if strata is None:
            continue
        for stratum_name, expected_count in (
            ("present", group["action_present_count"]),
            ("absent", group["action_absent_count"]),
        ):
            stratum = strata[stratum_name]
            if stratum["episode_count"] != expected_count:
                raise RCLValidationError(
                    f"{group_id}: {stratum_name} stratum count does not match group action count"
                )
            if expected_count == 0 and stratum["outcomes"]:
                raise RCLValidationError(
                    f"{group_id}: zero-count {stratum_name} stratum must not contain outcome statistics"
                )
            for outcome_id, stats in stratum["outcomes"].items():
                if outcome_id not in group["outcome_ids"]:
                    raise RCLValidationError(
                        f"{group_id}: stratum outcome {outcome_id!r} is not declared in outcome_ids"
                    )
                if stats["count"] != expected_count:
                    raise RCLValidationError(
                        f"{group_id}: {stratum_name} outcome {outcome_id!r} count does not match stratum count"
                    )

    if source_count != summary["source"]["episode_count"]:
        raise RCLValidationError(
            "Experience Summary group episode counts do not match source episode_count"
        )


def _build_report(
    hypothesis: dict[str, Any],
    *,
    total_episode_count: int,
    context_episode_count: int,
    ignored_episode_count: int,
    action_present_count: int,
    action_absent_count: int,
    present_mean: float | None,
    absent_mean: float | None,
    effective_policy: dict[str, Any],
    evidence_basis: str,
    evidence_provenance: dict[str, Any],
    created_at: str | None,
) -> dict[str, Any]:
    outcome = hypothesis["outcome"]
    outcome_type = outcome["type"]
    action_repeat_rate = (
        action_present_count / context_episode_count if context_episode_count else None
    )
    raw_difference = (
        present_mean - absent_mean
        if present_mean is not None and absent_mean is not None
        else None
    )
    beneficial_effect = (
        raw_difference
        if raw_difference is not None and outcome["higher_is_better"]
        else (-raw_difference if raw_difference is not None else None)
    )
    minimum_effect = float(outcome["minimum_meaningful_effect"])

    if beneficial_effect is None:
        effect_direction = "not_estimable"
    elif beneficial_effect >= minimum_effect:
        effect_direction = "beneficial"
    else:
        effect_direction = "neutral_or_harmful"

    min_context = int(effective_policy["min_context_episodes"])
    min_present = int(effective_policy["min_action_present"])
    min_absent = int(effective_policy["min_action_absent"])
    min_repeat = float(effective_policy["min_action_repeat_rate"])

    gates = [
        _gate(
            "context_episodes",
            actual=context_episode_count,
            required={"min": min_context},
            passed=context_episode_count >= min_context,
            reason="Enough episodes must match the declared context before an intent hypothesis can be reviewed.",
        ),
        _gate(
            "action_present_samples",
            actual=action_present_count,
            required={"min": min_present},
            passed=action_present_count >= min_present,
            reason="The candidate action needs repeated observed executions in the target context.",
        ),
        _gate(
            "action_absent_samples",
            actual=action_absent_count,
            required={"min": min_absent},
            passed=action_absent_count >= min_absent,
            reason="A comparison group without the candidate action is required for v0.1 association evidence.",
        ),
        _gate(
            "action_repeat_rate",
            actual=_rounded(action_repeat_rate),
            required={"min": min_repeat},
            passed=action_repeat_rate is not None and action_repeat_rate >= min_repeat,
            reason="The action must recur often enough in the declared context to be treated as a behavioral pattern.",
        ),
        _gate(
            "meaningful_outcome_association",
            actual=_rounded(beneficial_effect),
            required={"min": minimum_effect},
            passed=beneficial_effect is not None and beneficial_effect >= minimum_effect,
            reason="The action-present outcome must improve in the declared beneficial direction by at least the dataset-specific meaningful effect.",
        ),
    ]

    status = "candidate" if all(item["passed"] for item in gates) else "insufficient_evidence"

    if status == "candidate":
        sample_multiplier = float(effective_policy["strong_sample_multiplier"])
        effect_multiplier = float(effective_policy["strong_effect_multiplier"])
        strong = (
            context_episode_count >= ceil(min_context * sample_multiplier)
            and action_present_count >= ceil(min_present * sample_multiplier)
            and action_absent_count >= ceil(min_absent * sample_multiplier)
            and beneficial_effect is not None
            and beneficial_effect >= minimum_effect * effect_multiplier
        )
        confidence = "strong" if strong else "moderate"
        recommended_next_action = "review_candidate"
    else:
        confidence = "insufficient"
        recommended_next_action = "collect_more_evidence"

    report = {
        "discovery_version": INTENT_DISCOVERY_VERSION,
        "method": INTENT_DISCOVERY_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset_id": hypothesis["dataset_id"],
        "candidate_id": _candidate_id(hypothesis),
        "policy": {
            "policy_id": effective_policy["policy_id"],
            "policy_version": effective_policy["policy_version"],
        },
        "hypothesis": {
            "candidate_action_id": hypothesis["candidate_action_id"],
            "context_match": hypothesis["context_match"],
            "outcome": hypothesis["outcome"],
            "proposed_intent": hypothesis["proposed_intent"],
        },
        "evidence_basis": evidence_basis,
        "evidence_provenance": evidence_provenance,
        "evidence": {
            "total_episode_count": total_episode_count,
            "context_episode_count": context_episode_count,
            "ignored_episode_count": ignored_episode_count,
            "action_present_count": action_present_count,
            "action_absent_count": action_absent_count,
            "action_repeat_rate": _rounded(action_repeat_rate),
            "action_present_mean": _rounded(present_mean),
            "action_absent_mean": _rounded(absent_mean),
            "raw_difference": _rounded(raw_difference),
            "beneficial_effect": _rounded(beneficial_effect),
            "minimum_meaningful_effect": minimum_effect,
            "effect_direction": effect_direction,
            "outcome_type": outcome_type,
        },
        "gates": gates,
        "status": status,
        "confidence": confidence,
        "recommended_next_action": recommended_next_action,
        "causal_claim": False,
        "disclaimer": (
            "Intent Discovery v0.1 reports an association-backed engineering hypothesis only. "
            f"Evidence basis is {evidence_basis}; aggregate evidence is not reconstructed raw observation data. "
            "The report does not prove that the candidate action caused the observed outcome, does not establish subjective intent, "
            "and does not modify or approve an RCL behavior intent."
        ),
    }
    validate_schema(report, "intent-candidate-report")
    return report


def discover_intent_candidate(
    dataset: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate a generic raw context-action-outcome intent hypothesis.

    The function measures association only. It does not infer causality, invent a
    goal, mutate an RCL profile, or approve the proposed intent.
    """

    validate_schema(dataset, "intent-discovery-dataset")
    _validate_dataset_cross_fields(dataset)

    effective_policy = policy or load_default_intent_discovery_policy()
    validate_schema(effective_policy, "intent-discovery-policy")

    selector = dataset["context_match"]
    outcome = dataset["outcome"]
    outcome_id = outcome["outcome_id"]
    outcome_type = outcome["type"]

    context_episodes = [
        episode
        for episode in dataset["episodes"]
        if _matches_context(episode["context"], selector)
    ]

    present_values: list[float] = []
    absent_values: list[float] = []
    for episode in context_episodes:
        value = _outcome_value(
            episode["outcomes"][outcome_id],
            outcome_type,
            episode_id=episode["episode_id"],
            outcome_id=outcome_id,
        )
        if episode["action"]["performed"]:
            present_values.append(value)
        else:
            absent_values.append(value)

    total_episode_count = len(dataset["episodes"])
    context_episode_count = len(context_episodes)
    return _build_report(
        dataset,
        total_episode_count=total_episode_count,
        context_episode_count=context_episode_count,
        ignored_episode_count=total_episode_count - context_episode_count,
        action_present_count=len(present_values),
        action_absent_count=len(absent_values),
        present_mean=_mean(present_values),
        absent_mean=_mean(absent_values),
        effective_policy=effective_policy,
        evidence_basis="raw",
        evidence_provenance={
            "basis": "raw",
            "dataset_digest_sha256": _sha256_json(dataset),
            "source_episode_count": total_episode_count,
        },
        created_at=created_at,
    )


def _stratum_mean(
    group: dict[str, Any],
    *,
    stratum_name: str,
    outcome_id: str,
    expected_type: str,
) -> tuple[int, float | None]:
    strata = group.get("action_strata")
    if strata is None:
        raise RCLValidationError(
            f"{group['group_id']}: action-stratified outcome statistics are required for summary-aware Intent Discovery"
        )
    stratum = strata[stratum_name]
    count = int(stratum["episode_count"])
    if count == 0:
        return 0, None
    stats = stratum["outcomes"].get(outcome_id)
    if stats is None:
        raise RCLValidationError(
            f"{group['group_id']}: {stratum_name} stratum is missing outcome {outcome_id!r}"
        )
    if stats["type"] != expected_type:
        raise RCLValidationError(
            f"{group['group_id']}: outcome {outcome_id!r} type {stats['type']!r} does not match hypothesis type {expected_type!r}"
        )
    if stats["count"] != count:
        raise RCLValidationError(
            f"{group['group_id']}: {stratum_name} outcome count does not match stratum count"
        )
    value = stats["mean"] if expected_type == "numeric" else stats["true_rate"]
    return count, float(value)


def discover_intent_candidate_from_summary(
    summary: dict[str, Any],
    hypothesis: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate an intent hypothesis from action-stratified aggregate evidence.

    This function never reconstructs pseudo-episodes. It consumes only declared
    counts and aggregate outcome statistics produced by Experience Compaction.
    """

    validate_schema(summary, "experience-summary")
    validate_schema(hypothesis, "intent-summary-hypothesis")
    _validate_summary_cross_fields(summary)
    _validate_hypothesis(hypothesis)

    total_episode_count = int(summary["source"]["episode_count"])
    if total_episode_count < 2:
        raise RCLValidationError(
            "Summary-aware Intent Discovery requires at least two source episodes"
        )

    effective_policy = policy or load_default_intent_discovery_policy()
    validate_schema(effective_policy, "intent-discovery-policy")

    selector = hypothesis["context_match"]
    candidate_action_id = hypothesis["candidate_action_id"]
    outcome_id = hypothesis["outcome"]["outcome_id"]
    outcome_type = hypothesis["outcome"]["type"]

    matching_groups = [
        group
        for group in summary["groups"]
        if group["action_id"] == candidate_action_id
        and outcome_id in group["outcome_ids"]
        and _matches_context(group["context"], selector)
    ]
    if not matching_groups:
        raise RCLValidationError(
            "Experience Summary contains no groups matching the requested context, action, and outcome"
        )

    present_count = 0
    absent_count = 0
    present_weighted_sum = 0.0
    absent_weighted_sum = 0.0
    context_episode_count = 0

    for group in matching_groups:
        combined_stats = group["outcomes"].get(outcome_id)
        if combined_stats is None or combined_stats["type"] != outcome_type:
            actual = None if combined_stats is None else combined_stats["type"]
            raise RCLValidationError(
                f"{group['group_id']}: outcome {outcome_id!r} type {actual!r} does not match hypothesis type {outcome_type!r}"
            )

        group_present_count, group_present_mean = _stratum_mean(
            group,
            stratum_name="present",
            outcome_id=outcome_id,
            expected_type=outcome_type,
        )
        group_absent_count, group_absent_mean = _stratum_mean(
            group,
            stratum_name="absent",
            outcome_id=outcome_id,
            expected_type=outcome_type,
        )

        context_episode_count += int(group["episode_count"])
        present_count += group_present_count
        absent_count += group_absent_count
        if group_present_mean is not None:
            present_weighted_sum += group_present_mean * group_present_count
        if group_absent_mean is not None:
            absent_weighted_sum += group_absent_mean * group_absent_count

    present_mean = present_weighted_sum / present_count if present_count else None
    absent_mean = absent_weighted_sum / absent_count if absent_count else None

    return _build_report(
        hypothesis,
        total_episode_count=total_episode_count,
        context_episode_count=context_episode_count,
        ignored_episode_count=total_episode_count - context_episode_count,
        action_present_count=present_count,
        action_absent_count=absent_count,
        present_mean=present_mean,
        absent_mean=absent_mean,
        effective_policy=effective_policy,
        evidence_basis="aggregate",
        evidence_provenance={
            "basis": "aggregate",
            "summary_id": summary["summary_id"],
            "summary_method": summary["method"],
            "store_id": summary["source"]["store_id"],
            "source_digest_sha256": summary["source"]["source_digest_sha256"],
            "source_episode_count": total_episode_count,
            "group_ids": sorted(group["group_id"] for group in matching_groups),
        },
        created_at=created_at,
    )
