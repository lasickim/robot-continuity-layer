from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from typing import Any, Iterable

from .evaluation import validate_behavior_evaluation_metadata
from .profile import RCLProfile, RCLValidationError, validate_schema
from .score import PRIORITY_WEIGHTS


STATISTICAL_EVALUATION_VERSION = "0.2"
STATISTICAL_EVALUATION_METHOD = "rcl.observed.empirical_wasserstein.v0.2"
DEFAULT_MIN_TRIALS = 5


def _as_numeric_samples(values: Iterable[Any], *, label: str) -> list[float]:
    samples: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RCLValidationError(f"{label}: trial values must be numeric")
        samples.append(float(value))
    return samples


def sample_mean(samples: list[float]) -> float:
    if not samples:
        raise RCLValidationError("Cannot calculate mean of an empty sample")
    return sum(samples) / len(samples)


def sample_std(samples: list[float]) -> float:
    if len(samples) < 2:
        raise RCLValidationError("At least two samples are required for sample standard deviation")
    mean = sample_mean(samples)
    return sqrt(sum((value - mean) ** 2 for value in samples) / (len(samples) - 1))


def wasserstein_1d(source_samples: Iterable[float], target_samples: Iterable[float]) -> float:
    """Return the exact 1D Wasserstein-1 distance between two empirical samples.

    The implementation integrates the absolute difference between the two
    empirical CDFs. No external numerical dependency is required and unequal
    sample counts are supported.
    """

    source = sorted(float(value) for value in source_samples)
    target = sorted(float(value) for value in target_samples)
    if not source or not target:
        raise RCLValidationError("Wasserstein distance requires non-empty source and target samples")

    values = sorted(set(source + target))
    source_index = 0
    target_index = 0
    source_cdf = 0.0
    target_cdf = 0.0
    previous = values[0]
    distance = 0.0

    for value in values:
        distance += abs(source_cdf - target_cdf) * (value - previous)

        while source_index < len(source) and source[source_index] == value:
            source_index += 1
        while target_index < len(target) and target[target_index] == value:
            target_index += 1

        source_cdf = source_index / len(source)
        target_cdf = target_index / len(target)
        previous = value

    return distance


def _distance_similarity(distance: float, tolerance: float, zero_credit_at: float) -> float:
    if tolerance < 0:
        raise RCLValidationError("evaluation tolerance must be >= 0")
    if zero_credit_at <= tolerance:
        raise RCLValidationError("zero_credit_at must be greater than tolerance")
    if distance <= tolerance:
        return 1.0
    if distance >= zero_credit_at:
        return 0.0
    return 1.0 - ((distance - tolerance) / (zero_credit_at - tolerance))


def _trial_map(payload: dict[str, Any]) -> dict[str, dict[str, list[float]]]:
    result: dict[str, dict[str, list[float]]] = {}
    for behavior in payload["behavior_trials"]:
        behavior_id = behavior["behavior_id"]
        if behavior_id in result:
            raise RCLValidationError(f"Duplicate trial behavior: {behavior_id}")
        metrics: dict[str, list[float]] = {}
        for observable, values in behavior["metrics"].items():
            metrics[observable] = _as_numeric_samples(
                values,
                label=f"{behavior_id}.{observable}",
            )
        result[behavior_id] = metrics
    return result


def compare_trial_distributions(
    profile: RCLProfile,
    source_trials: dict[str, Any],
    target_trials: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Compare repeated source/target observations for declared RCL metrics."""

    validate_schema(source_trials, "trial-observations")
    validate_schema(target_trials, "trial-observations")

    behavior_payload = profile.load("behavior.json")
    validate_behavior_evaluation_metadata(behavior_payload)

    source_by_behavior = _trial_map(source_trials)
    target_by_behavior = _trial_map(target_trials)

    weighted_sum = 0.0
    total_weight = 0.0
    required_failures: list[str] = []
    metric_results: list[dict[str, Any]] = []
    declared_metric_count = 0

    for behavior in behavior_payload["behaviors"]:
        evaluation = behavior.get("evaluation")
        if evaluation is None:
            continue

        behavior_id = behavior["behavior_id"]
        priority = behavior["preservation"]["priority"]
        priority_weight = float(PRIORITY_WEIGHTS[priority])
        source_metrics = source_by_behavior.get(behavior_id, {})
        target_metrics = target_by_behavior.get(behavior_id, {})

        for metric in evaluation["metrics"]:
            declared_metric_count += 1
            metric_id = metric["metric_id"]
            observable = metric["observable"]
            tolerance = float(metric["tolerance"])
            zero_credit_at = float(metric["zero_credit_at"])
            metric_weight = float(metric["weight"])
            effective_weight = priority_weight * metric_weight
            required = bool(metric.get("required", True))
            min_trials = int(metric.get("min_trials", DEFAULT_MIN_TRIALS))
            if min_trials < 2:
                raise RCLValidationError(
                    f"{behavior_id}.{metric_id}: min_trials must be >= 2"
                )

            source_samples = source_metrics.get(observable)
            target_samples = target_metrics.get(observable)

            status: str | None = None
            if source_samples is None and target_samples is None:
                status = "missing_both"
            elif source_samples is None:
                status = "missing_source"
            elif target_samples is None:
                status = "missing_target"
            else:
                source_short = len(source_samples) < min_trials
                target_short = len(target_samples) < min_trials
                if source_short and target_short:
                    status = "insufficient_both"
                elif source_short:
                    status = "insufficient_source"
                elif target_short:
                    status = "insufficient_target"

            if status is not None:
                if required:
                    total_weight += effective_weight
                    required_failures.append(f"{behavior_id}.{metric_id}")
                metric_results.append(
                    {
                        "behavior_id": behavior_id,
                        "metric_id": metric_id,
                        "observable": observable,
                        "unit": metric["unit"],
                        "tolerance": tolerance,
                        "zero_credit_at": zero_credit_at,
                        "priority": priority,
                        "metric_weight": metric_weight,
                        "effective_weight": effective_weight,
                        "required": required,
                        "min_trials": min_trials,
                        "source_count": 0 if source_samples is None else len(source_samples),
                        "target_count": 0 if target_samples is None else len(target_samples),
                        "source_mean": None,
                        "source_std": None,
                        "target_mean": None,
                        "target_std": None,
                        "wasserstein_distance": None,
                        "status": status,
                        "similarity": 0.0 if required else None,
                    }
                )
                continue

            assert source_samples is not None and target_samples is not None
            source_mean = sample_mean(source_samples)
            target_mean = sample_mean(target_samples)
            source_std = sample_std(source_samples)
            target_std = sample_std(target_samples)
            distance = wasserstein_1d(source_samples, target_samples)
            similarity = _distance_similarity(distance, tolerance, zero_credit_at)

            total_weight += effective_weight
            weighted_sum += effective_weight * similarity

            if similarity == 1.0:
                status = "distribution_within_tolerance"
            elif similarity == 0.0:
                status = "distribution_outside_limit"
            else:
                status = "distribution_partial"

            if required and similarity == 0.0:
                required_failures.append(f"{behavior_id}.{metric_id}")

            metric_results.append(
                {
                    "behavior_id": behavior_id,
                    "metric_id": metric_id,
                    "observable": observable,
                    "unit": metric["unit"],
                    "tolerance": tolerance,
                    "zero_credit_at": zero_credit_at,
                    "priority": priority,
                    "metric_weight": metric_weight,
                    "effective_weight": effective_weight,
                    "required": required,
                    "min_trials": min_trials,
                    "source_count": len(source_samples),
                    "target_count": len(target_samples),
                    "source_mean": round(source_mean, 6),
                    "source_std": round(source_std, 6),
                    "target_mean": round(target_mean, 6),
                    "target_std": round(target_std, 6),
                    "wasserstein_distance": round(distance, 6),
                    "status": status,
                    "similarity": round(similarity, 6),
                }
            )

    if declared_metric_count == 0:
        raise RCLValidationError("Profile declares no observed evaluation metrics")
    if total_weight == 0:
        raise RCLValidationError("No repeated-trial metrics were available to score")

    score = round((weighted_sum / total_weight) * 100.0, 2)
    evaluation_success = len(required_failures) == 0
    if not evaluation_success:
        status = "failed"
    elif score == 100.0:
        status = "matched"
    else:
        status = "degraded"

    report = {
        "evaluation_version": STATISTICAL_EVALUATION_VERSION,
        "method": STATISTICAL_EVALUATION_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "robot_id": source_trials["robot_id"],
            "embodiment_id": source_trials["embodiment_id"],
            "captured_at": source_trials["captured_at"],
        },
        "target": {
            "robot_id": target_trials["robot_id"],
            "embodiment_id": target_trials["embodiment_id"],
            "captured_at": target_trials["captured_at"],
        },
        "score": score,
        "evaluation_success": evaluation_success,
        "status": status,
        "required_failures": required_failures,
        "metric_results": metric_results,
        "disclaimer": (
            "Experimental repeated-trial empirical distribution comparison only; "
            "not a formal hypothesis test, physical safety certification, or identity proof."
        ),
    }
    validate_schema(report, "statistical-continuity-report")
    return report
