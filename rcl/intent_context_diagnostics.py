from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from .profile import RCLValidationError


INTENT_CONTEXT_DIAGNOSTICS_VERSION = "0.1"
DEFAULT_MIN_STRATUM_ACTION_PRESENT = 2
DEFAULT_MIN_STRATUM_ACTION_ABSENT = 2
DEFAULT_ACTION_REPEAT_RATE_SPREAD = 0.5
_MISSING = object()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _beneficial_effect(
    present_mean: float | None,
    absent_mean: float | None,
    *,
    higher_is_better: bool,
) -> tuple[float | None, str]:
    if present_mean is None or absent_mean is None:
        return None, "not_estimable"
    raw = present_mean - absent_mean
    return (raw if higher_is_better else -raw), "estimated"


def _value_for_report(value: Any) -> Any:
    return None if value is _MISSING else value


def _field_value_keys(contexts: list[dict[str, Any]], selector: dict[str, Any]) -> list[str]:
    keys = set().union(*(context.keys() for context in contexts)) if contexts else set()
    return sorted(keys - set(selector))


def _summarize_field(
    field: str,
    buckets: dict[str, dict[str, Any]],
    *,
    minimum_effect: float,
    higher_is_better: bool,
    min_present: int,
    min_absent: int,
    action_rate_spread_threshold: float,
) -> dict[str, Any]:
    strata: list[dict[str, Any]] = []
    rates: list[float] = []
    supported_effects: list[float] = []
    supported_directions: list[str] = []

    for key in sorted(buckets):
        bucket = buckets[key]
        episode_count = int(bucket["episode_count"])
        present_count = int(bucket["present_count"])
        absent_count = int(bucket["absent_count"])
        present_mean = (
            bucket["present_sum"] / present_count if present_count else None
        )
        absent_mean = bucket["absent_sum"] / absent_count if absent_count else None
        effect, _ = _beneficial_effect(
            present_mean,
            absent_mean,
            higher_is_better=higher_is_better,
        )
        estimable = (
            present_count >= min_present
            and absent_count >= min_absent
            and effect is not None
        )
        if effect is None:
            direction = "not_estimable"
        elif effect >= minimum_effect:
            direction = "beneficial"
        else:
            direction = "neutral_or_harmful"

        repeat_rate = present_count / episode_count if episode_count else None
        if repeat_rate is not None:
            rates.append(repeat_rate)
        if estimable and effect is not None:
            supported_effects.append(effect)
            supported_directions.append(direction)

        strata.append(
            {
                "value": _value_for_report(bucket["value"]),
                "episode_count": episode_count,
                "action_present_count": present_count,
                "action_absent_count": absent_count,
                "action_repeat_rate": _rounded(repeat_rate),
                "action_present_mean": _rounded(present_mean),
                "action_absent_mean": _rounded(absent_mean),
                "beneficial_effect": _rounded(effect),
                "effect_direction": direction,
                "effect_estimable": estimable,
            }
        )

    rate_spread = max(rates) - min(rates) if len(rates) >= 2 else None
    action_prevalence_signal = (
        rate_spread is not None and rate_spread >= action_rate_spread_threshold
    )
    effect_spread = (
        max(supported_effects) - min(supported_effects)
        if len(supported_effects) >= 2
        else None
    )
    effect_heterogeneity_signal = (
        len(supported_directions) >= 2 and len(set(supported_directions)) > 1
    )
    supported_value_count = len(supported_effects)

    if action_prevalence_signal or effect_heterogeneity_signal:
        status = "context_dependency_signal"
    elif len(strata) >= 2 and supported_value_count < 2:
        status = "insufficient_context_coverage"
    else:
        status = "no_material_context_signal"

    reasons: list[str] = []
    if action_prevalence_signal:
        reasons.append("action_prevalence_varies_across_context_values")
    if effect_heterogeneity_signal:
        reasons.append("effect_direction_varies_across_supported_context_values")
    if status == "insufficient_context_coverage":
        reasons.append("fewer_than_two_context_values_have_supported_effect_estimates")
    if not reasons:
        reasons.append("no_material_context_dependency_detected")

    return {
        "field": field,
        "status": status,
        "value_count": len(strata),
        "supported_value_count": supported_value_count,
        "action_repeat_rate_spread": _rounded(rate_spread),
        "action_prevalence_signal": action_prevalence_signal,
        "beneficial_effect_spread": _rounded(effect_spread),
        "effect_heterogeneity_signal": effect_heterogeneity_signal,
        "reasons": reasons,
        "strata": strata,
    }


def _build_diagnostics(
    *,
    selector: dict[str, Any],
    contexts: list[dict[str, Any]],
    field_buckets: dict[str, dict[str, dict[str, Any]]],
    minimum_effect: float,
    higher_is_better: bool,
    min_present: int,
    min_absent: int,
    action_rate_spread_threshold: float,
    evidence_basis: str,
) -> dict[str, Any]:
    fields = []
    for field in _field_value_keys(contexts, selector):
        buckets = field_buckets.get(field, {})
        if len(buckets) < 2:
            continue
        fields.append(
            _summarize_field(
                field,
                buckets,
                minimum_effect=minimum_effect,
                higher_is_better=higher_is_better,
                min_present=min_present,
                min_absent=min_absent,
                action_rate_spread_threshold=action_rate_spread_threshold,
            )
        )

    warnings: list[str] = []
    for item in fields:
        if item["action_prevalence_signal"]:
            warnings.append(f"{item['field']}:action_prevalence_imbalance")
        if item["effect_heterogeneity_signal"]:
            warnings.append(f"{item['field']}:effect_heterogeneity")
        if item["status"] == "insufficient_context_coverage":
            warnings.append(f"{item['field']}:insufficient_context_coverage")

    if not fields:
        status = "no_residual_context_fields"
    elif any(item["status"] == "context_dependency_signal" for item in fields):
        status = "context_dependency_signal"
    elif any(item["status"] == "insufficient_context_coverage" for item in fields):
        status = "insufficient_context_coverage"
    else:
        status = "no_material_context_signal"

    return {
        "diagnostics_version": INTENT_CONTEXT_DIAGNOSTICS_VERSION,
        "evidence_basis": evidence_basis,
        "status": status,
        "review_required": status in {
            "context_dependency_signal",
            "insufficient_context_coverage",
        },
        "evaluated_fields": [item["field"] for item in fields],
        "thresholds": {
            "min_stratum_action_present": min_present,
            "min_stratum_action_absent": min_absent,
            "action_repeat_rate_spread": action_rate_spread_threshold,
            "minimum_meaningful_effect": minimum_effect,
        },
        "fields": fields,
        "warnings": sorted(warnings),
        "causal_claim": False,
    }


def evaluate_raw_context_diagnostics(
    dataset: dict[str, Any],
    context_episodes: list[dict[str, Any]],
    *,
    min_present: int = DEFAULT_MIN_STRATUM_ACTION_PRESENT,
    min_absent: int = DEFAULT_MIN_STRATUM_ACTION_ABSENT,
    action_rate_spread_threshold: float = DEFAULT_ACTION_REPEAT_RATE_SPREAD,
) -> dict[str, Any]:
    """Report context specificity for raw Intent Discovery evidence."""

    outcome = dataset["outcome"]
    outcome_id = outcome["outcome_id"]
    outcome_type = outcome["type"]
    selector = dataset["context_match"]
    contexts = [episode["context"] for episode in context_episodes]
    fields = _field_value_keys(contexts, selector)
    buckets: dict[str, dict[str, dict[str, Any]]] = {field: {} for field in fields}

    for episode in context_episodes:
        raw_value = episode["outcomes"][outcome_id]
        if outcome_type == "binary":
            if not isinstance(raw_value, bool):
                raise RCLValidationError(f"{episode['episode_id']}: binary diagnostic outcome must be boolean")
            value = 1.0 if raw_value else 0.0
        else:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise RCLValidationError(f"{episode['episode_id']}: numeric diagnostic outcome must be numeric")
            value = float(raw_value)

        for field in fields:
            context_value = episode["context"].get(field, _MISSING)
            key = _canonical(_value_for_report(context_value))
            bucket = buckets[field].setdefault(
                key,
                {
                    "value": context_value,
                    "episode_count": 0,
                    "present_count": 0,
                    "absent_count": 0,
                    "present_sum": 0.0,
                    "absent_sum": 0.0,
                },
            )
            bucket["episode_count"] += 1
            if episode["action"]["performed"]:
                bucket["present_count"] += 1
                bucket["present_sum"] += value
            else:
                bucket["absent_count"] += 1
                bucket["absent_sum"] += value

    return _build_diagnostics(
        selector=selector,
        contexts=contexts,
        field_buckets=buckets,
        minimum_effect=float(outcome["minimum_meaningful_effect"]),
        higher_is_better=bool(outcome["higher_is_better"]),
        min_present=min_present,
        min_absent=min_absent,
        action_rate_spread_threshold=action_rate_spread_threshold,
        evidence_basis="raw",
    )


def evaluate_aggregate_context_diagnostics(
    hypothesis: dict[str, Any],
    matching_groups: list[dict[str, Any]],
    *,
    min_present: int = DEFAULT_MIN_STRATUM_ACTION_PRESENT,
    min_absent: int = DEFAULT_MIN_STRATUM_ACTION_ABSENT,
    action_rate_spread_threshold: float = DEFAULT_ACTION_REPEAT_RATE_SPREAD,
) -> dict[str, Any]:
    """Report context specificity from aggregate groups without pseudo-episodes."""

    outcome = hypothesis["outcome"]
    outcome_id = outcome["outcome_id"]
    outcome_type = outcome["type"]
    selector = hypothesis["context_match"]
    contexts = [group["context"] for group in matching_groups]
    fields = _field_value_keys(contexts, selector)
    buckets: dict[str, dict[str, dict[str, Any]]] = {field: {} for field in fields}

    for group in matching_groups:
        strata = group.get("action_strata")
        if strata is None:
            raise RCLValidationError(
                f"{group['group_id']}: action_strata required for aggregate context diagnostics"
            )
        present_count = int(strata["present"]["episode_count"])
        absent_count = int(strata["absent"]["episode_count"])

        def stratum_mean(name: str, count: int) -> float | None:
            if count == 0:
                return None
            stats = strata[name]["outcomes"].get(outcome_id)
            if stats is None or stats["type"] != outcome_type:
                raise RCLValidationError(
                    f"{group['group_id']}: incompatible aggregate diagnostic outcome {outcome_id!r}"
                )
            return float(stats["mean"] if outcome_type == "numeric" else stats["true_rate"])

        present_mean = stratum_mean("present", present_count)
        absent_mean = stratum_mean("absent", absent_count)

        for field in fields:
            context_value = group["context"].get(field, _MISSING)
            key = _canonical(_value_for_report(context_value))
            bucket = buckets[field].setdefault(
                key,
                {
                    "value": context_value,
                    "episode_count": 0,
                    "present_count": 0,
                    "absent_count": 0,
                    "present_sum": 0.0,
                    "absent_sum": 0.0,
                },
            )
            bucket["episode_count"] += int(group["episode_count"])
            bucket["present_count"] += present_count
            bucket["absent_count"] += absent_count
            if present_mean is not None:
                bucket["present_sum"] += present_mean * present_count
            if absent_mean is not None:
                bucket["absent_sum"] += absent_mean * absent_count

    return _build_diagnostics(
        selector=selector,
        contexts=contexts,
        field_buckets=buckets,
        minimum_effect=float(outcome["minimum_meaningful_effect"]),
        higher_is_better=bool(outcome["higher_is_better"]),
        min_present=min_present,
        min_absent=min_absent,
        action_rate_spread_threshold=action_rate_spread_threshold,
        evidence_basis="aggregate",
    )
