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


def _candidate_id(dataset: dict[str, Any]) -> str:
    material = {
        "dataset_id": dataset["dataset_id"],
        "candidate_action_id": dataset["candidate_action_id"],
        "context_match": dataset["context_match"],
        "outcome_id": dataset["outcome"]["outcome_id"],
        "goal_id": dataset["proposed_intent"]["goal_id"],
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


def _validate_hypothesis(dataset: dict[str, Any]) -> None:
    # Reuse the same goal/capability vocabulary checks as a real behavior intent
    # without mutating or constructing an RCL profile.
    synthetic = {
        "behaviors": [
            {
                "behavior_id": "x.rcl.intent_discovery_candidate",
                "parameters": {},
                "preservation": {"priority": "optional", "mode": "semantic"},
                "intent": dataset["proposed_intent"],
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


def discover_intent_candidate(
    dataset: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate a generic context-action-outcome intent hypothesis.

    The function measures association only. It does not infer causality, invent a
    goal, mutate an RCL profile, or approve the proposed intent.
    """

    validate_schema(dataset, "intent-discovery-dataset")
    _validate_dataset_cross_fields(dataset)

    effective_policy = policy or load_default_intent_discovery_policy()
    validate_schema(effective_policy, "intent-discovery-policy")

    selector = dataset["context_match"]
    candidate_action_id = dataset["candidate_action_id"]
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
    ignored_episode_count = total_episode_count - context_episode_count
    action_present_count = len(present_values)
    action_absent_count = len(absent_values)
    action_repeat_rate = (
        action_present_count / context_episode_count if context_episode_count else None
    )

    present_mean = _mean(present_values)
    absent_mean = _mean(absent_values)
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
        "dataset_id": dataset["dataset_id"],
        "candidate_id": _candidate_id(dataset),
        "policy": {
            "policy_id": effective_policy["policy_id"],
            "policy_version": effective_policy["policy_version"],
        },
        "hypothesis": {
            "candidate_action_id": candidate_action_id,
            "context_match": dataset["context_match"],
            "outcome": dataset["outcome"],
            "proposed_intent": dataset["proposed_intent"],
        },
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
            "It does not prove that the candidate action caused the observed outcome, does not establish subjective intent, "
            "and does not modify or approve an RCL behavior intent."
        ),
    }
    validate_schema(report, "intent-candidate-report")
    return report
