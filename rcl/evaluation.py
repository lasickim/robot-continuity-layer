from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .profile import RCLProfile, RCLValidationError, validate_schema
from .score import PRIORITY_WEIGHTS


EVALUATION_VERSION = "0.1"
EVALUATION_METHOD = "rcl.observed.numeric_tolerance.v0.1"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _metric_similarity(error: float, tolerance: float, zero_credit_at: float) -> float:
    if tolerance < 0:
        raise RCLValidationError("evaluation tolerance must be >= 0")
    if zero_credit_at <= tolerance:
        raise RCLValidationError("zero_credit_at must be greater than tolerance")
    if error <= tolerance:
        return 1.0
    if error >= zero_credit_at:
        return 0.0
    return 1.0 - ((error - tolerance) / (zero_credit_at - tolerance))


def validate_behavior_evaluation_metadata(behavior_payload: dict[str, Any]) -> None:
    """Validate v0.3-dev evaluation metadata that JSON Schema cannot cross-check.

    Evaluation targets intentionally reference existing semantic behavior parameters
    so a tolerance definition does not duplicate the canonical target value.
    """

    for behavior in behavior_payload.get("behaviors", []):
        evaluation = behavior.get("evaluation")
        if evaluation is None:
            continue

        metric_ids: set[str] = set()
        parameters = behavior.get("parameters", {})
        for metric in evaluation.get("metrics", []):
            metric_id = metric["metric_id"]
            if metric_id in metric_ids:
                raise RCLValidationError(
                    f"{behavior['behavior_id']}: duplicate evaluation metric_id {metric_id}"
                )
            metric_ids.add(metric_id)

            target_parameter = metric["target_parameter"]
            if target_parameter not in parameters:
                raise RCLValidationError(
                    f"{behavior['behavior_id']}.{metric_id}: target_parameter "
                    f"{target_parameter!r} does not exist in behavior parameters"
                )
            if not _is_number(parameters[target_parameter]):
                raise RCLValidationError(
                    f"{behavior['behavior_id']}.{metric_id}: target_parameter "
                    f"{target_parameter!r} must resolve to a numeric value"
                )

            tolerance = float(metric["tolerance"])
            zero_credit_at = float(metric["zero_credit_at"])
            if zero_credit_at <= tolerance:
                raise RCLValidationError(
                    f"{behavior['behavior_id']}.{metric_id}: zero_credit_at must be "
                    "greater than tolerance"
                )


def evaluate_observed_continuity(
    profile: RCLProfile,
    observations: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate observed target behavior against declared RCL tolerances.

    This v0.1 evaluator is deliberately narrow: it scores numeric observations
    against a semantic target parameter using an absolute tolerance band and a
    linear falloff to zero credit.
    """

    validate_schema(observations, "observations")

    behavior_payload = profile.load("behavior.json")
    source_identity = profile.load("identity.json")
    source_embodiment = profile.load("embodiment.json")
    validate_behavior_evaluation_metadata(behavior_payload)

    observed_by_behavior: dict[str, dict[str, Any]] = {}
    for item in observations["behavior_observations"]:
        behavior_id = item["behavior_id"]
        if behavior_id in observed_by_behavior:
            raise RCLValidationError(
                f"Duplicate behavior observation: {behavior_id}"
            )
        observed_by_behavior[behavior_id] = item["metrics"]

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
        observed_metrics = observed_by_behavior.get(behavior_id, {})

        for metric in evaluation["metrics"]:
            declared_metric_count += 1
            metric_id = metric["metric_id"]
            observable = metric["observable"]
            target = float(behavior["parameters"][metric["target_parameter"]])
            tolerance = float(metric["tolerance"])
            zero_credit_at = float(metric["zero_credit_at"])
            metric_weight = float(metric["weight"])
            required = bool(metric.get("required", True))
            effective_weight = priority_weight * metric_weight

            if observable not in observed_metrics:
                status = "missing" if required else "missing_optional"
                if required:
                    total_weight += effective_weight
                    required_failures.append(f"{behavior_id}.{metric_id}")
                metric_results.append(
                    {
                        "behavior_id": behavior_id,
                        "metric_id": metric_id,
                        "observable": observable,
                        "target": target,
                        "observed": None,
                        "unit": metric["unit"],
                        "tolerance": tolerance,
                        "zero_credit_at": zero_credit_at,
                        "priority": priority,
                        "metric_weight": metric_weight,
                        "effective_weight": effective_weight,
                        "status": status,
                        "similarity": None if not required else 0.0,
                        "absolute_error": None,
                        "required": required,
                    }
                )
                continue

            observed = float(observed_metrics[observable])
            error = abs(observed - target)
            similarity = _metric_similarity(error, tolerance, zero_credit_at)
            total_weight += effective_weight
            weighted_sum += effective_weight * similarity

            if similarity == 1.0:
                status = "within_tolerance"
            elif similarity == 0.0:
                status = "outside_limit"
            else:
                status = "partial"

            if required and similarity == 0.0:
                required_failures.append(f"{behavior_id}.{metric_id}")

            metric_results.append(
                {
                    "behavior_id": behavior_id,
                    "metric_id": metric_id,
                    "observable": observable,
                    "target": target,
                    "observed": observed,
                    "unit": metric["unit"],
                    "tolerance": tolerance,
                    "zero_credit_at": zero_credit_at,
                    "priority": priority,
                    "metric_weight": metric_weight,
                    "effective_weight": effective_weight,
                    "status": status,
                    "similarity": round(similarity, 6),
                    "absolute_error": round(error, 6),
                    "required": required,
                }
            )

    if declared_metric_count == 0:
        raise RCLValidationError("Profile declares no observed evaluation metrics")
    if total_weight == 0:
        raise RCLValidationError("No observed evaluation metrics were available to score")

    score = round((weighted_sum / total_weight) * 100.0, 2)
    evaluation_success = len(required_failures) == 0
    if not evaluation_success:
        status = "failed"
    elif score == 100.0:
        status = "within_tolerance"
    else:
        status = "degraded"

    report = {
        "evaluation_version": EVALUATION_VERSION,
        "method": EVALUATION_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "robot_id": source_identity["robot_id"],
            "embodiment_id": source_embodiment["embodiment_id"],
        },
        "target": {
            "robot_id": observations["robot_id"],
            "embodiment_id": observations["embodiment_id"],
            "captured_at": observations["captured_at"],
        },
        "score": score,
        "evaluation_success": evaluation_success,
        "status": status,
        "required_failures": required_failures,
        "metric_results": metric_results,
        "disclaimer": (
            "Experimental observed-vs-declared continuity evaluation only; "
            "not physical safety certification or source/target statistical identity proof."
        ),
    }
    validate_schema(report, "observed-evaluation-report")
    return report
