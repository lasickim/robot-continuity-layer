from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from typing import Any

from .experiment_context import DEFAULT_COMPARISON_FIELDS
from .profile import RCLProfile, RCLValidationError, validate_schema
from .statistical_evaluation import compare_trial_distributions, sample_mean, sample_std


SESSION_EVALUATION_VERSION = "0.1"
SESSION_EVALUATION_METHOD = "rcl.observed.session_mean_t95.v0.1"
DEFAULT_MIN_SESSIONS = 3
CONFIDENCE_LEVEL = 0.95

_T95_CRITICAL = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def t95_critical(df: int) -> float:
    if df < 1:
        raise RCLValidationError("Student-t confidence interval requires df >= 1")
    if df <= 30:
        return _T95_CRITICAL[df]
    if df <= 40:
        return 2.021
    if df <= 60:
        return 2.000
    if df <= 120:
        return 1.980
    return 1.960


def confidence_interval_95(
    values: list[float],
    *,
    lower_bound: float,
    upper_bound: float,
) -> dict[str, float]:
    if len(values) < 2:
        raise RCLValidationError("At least two values are required for a confidence interval")
    mean = sample_mean(values)
    std = sample_std(values)
    critical = t95_critical(len(values) - 1)
    half_width = critical * std / sqrt(len(values))
    return {
        "low": round(max(lower_bound, mean - half_width), 6),
        "high": round(min(upper_bound, mean + half_width), 6),
        "half_width": round(half_width, 6),
        "critical_value": round(critical, 6),
    }


def _series_signature(pair: dict[str, Any]) -> dict[str, Any]:
    source = pair["source_trials"]
    target = pair["target_trials"]
    source_experiment = source["experiment"]
    protocol = source_experiment["protocol"]
    context = source_experiment["context"]
    fields = list(protocol.get("comparison_fields") or DEFAULT_COMPARISON_FIELDS)
    return {
        "source_robot_id": source["robot_id"],
        "source_embodiment_id": source["embodiment_id"],
        "target_robot_id": target["robot_id"],
        "target_embodiment_id": target["embodiment_id"],
        "protocol_id": protocol["protocol_id"],
        "protocol_version": protocol["protocol_version"],
        "comparison_fields": fields,
        "comparison_context": {field: context.get(field) for field in fields},
    }


def _compare_series_signature(
    reference_session_id: str,
    reference: dict[str, Any],
    session_id: str,
    observed: dict[str, Any],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for field in (
        "source_robot_id",
        "source_embodiment_id",
        "target_robot_id",
        "target_embodiment_id",
        "protocol_id",
        "protocol_version",
        "comparison_fields",
        "comparison_context",
    ):
        if reference[field] != observed[field]:
            mismatches.append(
                {
                    "session_id": session_id,
                    "field": field,
                    "reference_session_id": reference_session_id,
                    "reference": reference[field],
                    "observed": observed[field],
                }
            )
    return mismatches


def _metric_summaries(
    buckets: dict[tuple[str, str, str], list[float]],
    *,
    min_sessions: int,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for (behavior_id, metric_id, unit), similarities in sorted(buckets.items()):
        count = len(similarities)
        mean_similarity = sample_mean(similarities)
        std_similarity = sample_std(similarities) if count >= 2 else None
        ci = (
            confidence_interval_95(
                similarities,
                lower_bound=0.0,
                upper_bound=1.0,
            )
            if count >= min_sessions
            else None
        )
        summaries.append(
            {
                "behavior_id": behavior_id,
                "metric_id": metric_id,
                "unit": unit,
                "session_count": count,
                "mean_similarity": round(mean_similarity, 6),
                "similarity_std": None if std_similarity is None else round(std_similarity, 6),
                "confidence_interval_95": ci,
            }
        )
    return summaries


def evaluate_repeated_sessions(
    profile: RCLProfile,
    session_pairs: list[dict[str, Any]],
    *,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Aggregate repeated Robot A ↔ Robot B session comparisons with uncertainty.

    Each session is an equal-weight unit regardless of the number of trials inside
    that session. The function reuses the existing context-gated statistical
    evaluator and reports a 95% Student-t confidence interval over session scores.
    """

    if min_sessions < 3:
        raise RCLValidationError("min_sessions must be >= 3")
    if not session_pairs:
        raise RCLValidationError("At least one session pair is required")

    seen_session_ids: set[str] = set()
    session_results: list[dict[str, Any]] = []
    score_values: list[float] = []
    metric_buckets: dict[tuple[str, str, str], list[float]] = {}
    failed_session_ids: list[str] = []
    context_mismatch_session_ids: list[str] = []
    reference_session_id: str | None = None
    reference_signature: dict[str, Any] | None = None
    series_mismatches: list[dict[str, Any]] = []

    for pair in session_pairs:
        session_id = pair.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise RCLValidationError("Each repeated-session pair requires a non-empty session_id")
        if session_id in seen_session_ids:
            raise RCLValidationError(f"Duplicate session_id: {session_id}")
        seen_session_ids.add(session_id)

        source_trials = pair.get("source_trials")
        target_trials = pair.get("target_trials")
        if not isinstance(source_trials, dict) or not isinstance(target_trials, dict):
            raise RCLValidationError(f"{session_id}: source_trials and target_trials must be objects")

        session_report = compare_trial_distributions(
            profile,
            source_trials,
            target_trials,
        )
        context_compatible = bool(session_report["context_comparison"]["compatible"])

        if context_compatible:
            signature = _series_signature(pair)
            if reference_signature is None:
                reference_signature = signature
                reference_session_id = session_id
            else:
                assert reference_session_id is not None
                series_mismatches.extend(
                    _compare_series_signature(
                        reference_session_id,
                        reference_signature,
                        session_id,
                        signature,
                    )
                )

        score = session_report["score"]
        if score is not None:
            score_values.append(float(score))
        if not session_report["evaluation_success"]:
            failed_session_ids.append(session_id)
        if not context_compatible:
            context_mismatch_session_ids.append(session_id)

        for metric in session_report["metric_results"]:
            similarity = metric["similarity"]
            if similarity is None:
                continue
            key = (metric["behavior_id"], metric["metric_id"], metric["unit"])
            metric_buckets.setdefault(key, []).append(float(similarity))

        session_results.append(
            {
                "session_id": session_id,
                "score": score,
                "evaluation_success": session_report["evaluation_success"],
                "status": session_report["status"],
                "context_compatible": context_compatible,
                "required_failures": session_report["required_failures"],
                "source_session_id": session_report["source"]["session_id"],
                "target_session_id": session_report["target"]["session_id"],
            }
        )

    series_comparison = {
        "compatible": not series_mismatches,
        "reference_session_id": reference_session_id,
        "mismatches": series_mismatches,
    }

    total_session_count = len(session_pairs)
    scorable_session_count = len(score_values)
    successful_session_count = sum(1 for item in session_results if item["evaluation_success"])
    failed_session_count = total_session_count - successful_session_count

    mean_score: float | None = None
    score_std: float | None = None
    score_ci: dict[str, float] | None = None
    metric_summaries: list[dict[str, Any]] = []

    if series_mismatches:
        status = "series_mismatch"
        evaluation_success = False
    elif scorable_session_count == 0:
        status = "no_scorable_sessions"
        evaluation_success = False
    else:
        mean_score = round(sample_mean(score_values), 6)
        if scorable_session_count >= 2:
            score_std = round(sample_std(score_values), 6)
        if scorable_session_count >= min_sessions:
            score_ci = confidence_interval_95(
                score_values,
                lower_bound=0.0,
                upper_bound=100.0,
            )
        metric_summaries = _metric_summaries(metric_buckets, min_sessions=min_sessions)

        if failed_session_count > 0:
            status = "session_failures"
            evaluation_success = False
        elif scorable_session_count < min_sessions:
            status = "insufficient_sessions"
            evaluation_success = False
        else:
            status = "estimated"
            evaluation_success = True

    report = {
        "session_evaluation_version": SESSION_EVALUATION_VERSION,
        "method": SESSION_EVALUATION_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "confidence_level": CONFIDENCE_LEVEL,
        "min_sessions": min_sessions,
        "total_session_count": total_session_count,
        "scorable_session_count": scorable_session_count,
        "successful_session_count": successful_session_count,
        "failed_session_count": failed_session_count,
        "failed_session_ids": failed_session_ids,
        "context_mismatch_session_ids": context_mismatch_session_ids,
        "series_comparison": series_comparison,
        "mean_score": mean_score,
        "score_std": score_std,
        "confidence_interval_95": score_ci,
        "evaluation_success": evaluation_success,
        "status": status,
        "session_results": session_results,
        "metric_summaries": metric_summaries,
        "disclaimer": (
            "Experimental uncertainty estimate across equally weighted session-level continuity scores. "
            "It does not define a universal acceptance threshold, physical safety certification, or identity proof."
        ),
    }
    validate_schema(report, "session-evaluation-report")
    return report
