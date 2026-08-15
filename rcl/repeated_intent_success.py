from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from typing import Any

from .intent_success_evaluation import evaluate_observed_intent_success
from .profile import RCLProfile, RCLValidationError, validate_schema
from .session_evaluation import confidence_interval_95
from .statistical_evaluation import sample_mean, sample_std


REPEATED_INTENT_SUCCESS_VERSION = "0.1"
REPEATED_INTENT_SUCCESS_METHOD = "rcl.observed.intent_success.repeated.v0.1"
DEFAULT_MIN_OBSERVABLE_TRIALS = 3
DEFAULT_MIN_SESSIONS = 3
CONFIDENCE_LEVEL = 0.95
_WILSON_Z95 = 1.959963984540054


def wilson_interval_95(successes: int, total: int) -> dict[str, float] | None:
    """Return a deterministic 95% Wilson interval for a binomial proportion."""

    if successes < 0 or total < 0 or successes > total:
        raise RCLValidationError("Wilson interval requires 0 <= successes <= total")
    if total == 0:
        return None

    z = _WILSON_Z95
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    half_width = (
        z
        * sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total)
        / denominator
    )
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return {
        "low": round(low, 6),
        "high": round(high, 6),
        "half_width": round(half_width, 6),
    }


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if parsed.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return parsed


def _validated_sessions(series: dict[str, Any]) -> list[dict[str, Any]]:
    validate_schema(series, "intent-observation-series")

    seen_session_ids: set[str] = set()
    seen_trial_ids: set[str] = set()
    seen_observation_ids: set[str] = set()
    total_trials = 0
    normalized: list[dict[str, Any]] = []

    for session in series["sessions"]:
        session_id = session["session_id"]
        if session_id in seen_session_ids:
            raise RCLValidationError(f"Duplicate intent-series session_id: {session_id}")
        seen_session_ids.add(session_id)
        started_at = _parse_datetime(
            session["started_at"], label=f"session {session_id} started_at"
        )

        trials: list[dict[str, Any]] = []
        for trial in session["trials"]:
            trial_id = trial["trial_id"]
            if trial_id in seen_trial_ids:
                raise RCLValidationError(f"Duplicate intent-series trial_id: {trial_id}")
            seen_trial_ids.add(trial_id)
            captured_at = _parse_datetime(
                trial["captured_at"], label=f"trial {trial_id} captured_at"
            )
            if captured_at < started_at:
                raise RCLValidationError(
                    f"{trial_id}: captured_at must not precede session started_at"
                )

            for observation in trial["intent_observations"]:
                observation_id = observation["observation_id"]
                if observation_id in seen_observation_ids:
                    raise RCLValidationError(
                        f"Duplicate intent-series observation_id: {observation_id}"
                    )
                seen_observation_ids.add(observation_id)

            trials.append(trial)
            total_trials += 1

        normalized.append(
            {
                **session,
                "trials": sorted(
                    trials,
                    key=lambda item: (
                        _parse_datetime(
                            item["captured_at"],
                            label=f"trial {item['trial_id']} captured_at",
                        ),
                        item["trial_id"],
                    ),
                ),
            }
        )

    if total_trials < 2:
        raise RCLValidationError(
            "Repeated Intent Success requires at least two trials across the series"
        )

    return sorted(
        normalized,
        key=lambda item: (
            _parse_datetime(
                item["started_at"], label=f"session {item['session_id']} started_at"
            ),
            item["session_id"],
        ),
    )


def _empty_counts() -> dict[str, int]:
    return {
        "pass_count": 0,
        "fail_count": 0,
        "not_observable_count": 0,
        "not_triggered_count": 0,
        "missing_observation_count": 0,
    }


def _add_result(counts: dict[str, int], result: dict[str, Any]) -> None:
    status = result["status"]
    counts[f"{status}_count"] += 1
    if result["reason"] == "missing_observation":
        counts["missing_observation_count"] += 1


def _rates(counts: dict[str, int]) -> dict[str, Any]:
    observable = counts["pass_count"] + counts["fail_count"]
    total = (
        observable
        + counts["not_observable_count"]
        + counts["not_triggered_count"]
    )
    triggered = observable + (
        counts["not_observable_count"] - counts["missing_observation_count"]
    )
    success_rate = None if observable == 0 else round(counts["pass_count"] / observable, 6)
    return {
        "total_trial_count": total,
        "triggered_trial_count": triggered,
        "observable_trial_count": observable,
        "observable_rate": None if total == 0 else round(observable / total, 6),
        "observed_success_rate": success_rate,
        "wilson_interval_95": wilson_interval_95(counts["pass_count"], observable),
    }


def _session_intent_summary(
    session_id: str,
    behavior_id: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = _empty_counts()
    strategies: set[str] = set()
    for result in results:
        _add_result(counts, result)
        if result.get("strategy_id"):
            strategies.add(result["strategy_id"])

    rates = _rates(counts)
    if counts["fail_count"]:
        status = "observed_failures"
    elif rates["observable_trial_count"] == 0:
        status = "insufficient_evidence"
    else:
        status = "observed"

    return {
        "session_id": session_id,
        "behavior_id": behavior_id,
        **counts,
        **rates,
        "observed_strategy_ids": sorted(strategies),
        "status": status,
    }


def _intent_summary(
    behavior_id: str,
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
    session_results: dict[str, list[dict[str, Any]]],
    *,
    min_observable_trials: int,
    min_sessions: int,
) -> dict[str, Any]:
    counts = _empty_counts()
    strategies: set[str] = set()
    for result in results:
        _add_result(counts, result)
        if result.get("strategy_id"):
            strategies.add(result["strategy_id"])

    rates = _rates(counts)
    session_summaries = [
        _session_intent_summary(session_id, behavior_id, session_results[session_id])
        for session_id in sorted(session_results)
    ]
    session_rates = [
        float(item["observed_success_rate"])
        for item in session_summaries
        if item["observed_success_rate"] is not None
    ]
    mean_session_rate = (
        None if not session_rates else round(sample_mean(session_rates), 6)
    )
    session_rate_std = (
        None if len(session_rates) < 2 else round(sample_std(session_rates), 6)
    )
    session_ci = (
        confidence_interval_95(
            session_rates,
            lower_bound=0.0,
            upper_bound=1.0,
        )
        if len(session_rates) >= min_sessions
        else None
    )

    criticality = metadata["criticality"]
    if counts["fail_count"]:
        status = "observed_failures"
    elif rates["observable_trial_count"] < min_observable_trials:
        status = "insufficient_evidence"
    else:
        status = "estimated"
    blocking = criticality == "required" and status != "estimated"

    return {
        "behavior_id": behavior_id,
        "goal_id": metadata["goal_id"],
        "criticality": criticality,
        "trigger": metadata["trigger"],
        "success_condition": metadata["success_condition"],
        **counts,
        **rates,
        "observed_strategy_ids": sorted(strategies),
        "session_count": len(session_summaries),
        "scorable_session_count": len(session_rates),
        "mean_session_success_rate": mean_session_rate,
        "session_success_rate_std": session_rate_std,
        "session_confidence_interval_95": session_ci,
        "status": status,
        "blocking": blocking,
        "session_summaries": session_summaries,
    }


def evaluate_repeated_intent_success(
    profile: RCLProfile,
    series: dict[str, Any],
    *,
    min_observable_trials: int = DEFAULT_MIN_OBSERVABLE_TRIALS,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate repeated observed satisfaction of declared engineering Intent.

    Every trial is first evaluated by Observed Intent Success v0.1. This keeps
    trigger/success-condition semantics identical to the single-run evaluator.
    Pooled pass/fail evidence receives a Wilson 95% interval. Session rates are
    also summarized as equal-weight observations, with a Student-t interval once
    enough sessions exist. No universal success-rate threshold is introduced.
    """

    if min_observable_trials < 2:
        raise RCLValidationError("min_observable_trials must be >= 2")
    if min_sessions < 3:
        raise RCLValidationError("min_sessions must be >= 3")

    sessions = _validated_sessions(series)
    all_by_behavior: dict[str, list[dict[str, Any]]] = {}
    by_session_behavior: dict[str, dict[str, list[dict[str, Any]]]] = {}
    metadata_by_behavior: dict[str, dict[str, Any]] = {}
    session_outputs: list[dict[str, Any]] = []
    total_trial_count = 0

    for session in sessions:
        session_id = session["session_id"]
        by_session_behavior[session_id] = {}
        trial_statuses: list[dict[str, Any]] = []
        required_failures: set[str] = set()
        required_inconclusive: set[str] = set()
        nonblocking_failures: set[str] = set()

        for trial in session["trials"]:
            observations = {
                "intent_observation_version": "0.1",
                "robot_id": series["robot_id"],
                "embodiment_id": series["embodiment_id"],
                "captured_at": trial["captured_at"],
                "intent_observations": trial["intent_observations"],
            }
            trial_report = evaluate_observed_intent_success(
                profile,
                observations,
                created_at=trial["captured_at"],
            )
            total_trial_count += 1
            trial_statuses.append(
                {
                    "trial_id": trial["trial_id"],
                    "captured_at": trial["captured_at"],
                    "status": trial_report["status"],
                    "evaluation_success": trial_report["evaluation_success"],
                    "required_failures": list(trial_report["required_failures"]),
                    "required_inconclusive": list(trial_report["required_inconclusive"]),
                    "nonblocking_failures": list(trial_report["nonblocking_failures"]),
                }
            )
            required_failures.update(trial_report["required_failures"])
            required_inconclusive.update(trial_report["required_inconclusive"])
            nonblocking_failures.update(trial_report["nonblocking_failures"])

            for result in trial_report["intent_results"]:
                behavior_id = result["behavior_id"]
                metadata_by_behavior.setdefault(
                    behavior_id,
                    {
                        "goal_id": result["goal_id"],
                        "criticality": result["criticality"],
                        "trigger": result["trigger"],
                        "success_condition": result["success_condition"],
                    },
                )
                all_by_behavior.setdefault(behavior_id, []).append(result)
                by_session_behavior[session_id].setdefault(behavior_id, []).append(result)

        if required_failures:
            session_status = "failed"
            session_success: bool | None = False
        elif required_inconclusive:
            session_status = "inconclusive"
            session_success = None
        else:
            session_status = "passed"
            session_success = True

        session_outputs.append(
            {
                "session_id": session_id,
                "started_at": session["started_at"],
                "trial_count": len(session["trials"]),
                "status": session_status,
                "evaluation_success": session_success,
                "required_failures": sorted(required_failures),
                "required_inconclusive": sorted(required_inconclusive),
                "nonblocking_failures": sorted(nonblocking_failures),
                "trial_results": trial_statuses,
            }
        )

    intent_summaries = [
        _intent_summary(
            behavior_id,
            metadata_by_behavior[behavior_id],
            all_by_behavior[behavior_id],
            {
                session_id: by_session_behavior[session_id][behavior_id]
                for session_id in by_session_behavior
            },
            min_observable_trials=min_observable_trials,
            min_sessions=min_sessions,
        )
        for behavior_id in sorted(all_by_behavior)
    ]

    required_failures = [
        item["behavior_id"]
        for item in intent_summaries
        if item["criticality"] == "required" and item["fail_count"] > 0
    ]
    required_inconclusive = [
        item["behavior_id"]
        for item in intent_summaries
        if item["criticality"] == "required"
        and item["fail_count"] == 0
        and item["observable_trial_count"] < min_observable_trials
    ]
    nonblocking_failures = [
        item["behavior_id"]
        for item in intent_summaries
        if item["criticality"] != "required" and item["fail_count"] > 0
    ]
    nonblocking_inconclusive = [
        item["behavior_id"]
        for item in intent_summaries
        if item["criticality"] != "required"
        and item["observable_trial_count"] < min_observable_trials
    ]

    if required_failures:
        status = "failed"
        evaluation_success: bool | None = False
    elif required_inconclusive:
        status = "inconclusive"
        evaluation_success = None
    else:
        status = "estimated"
        evaluation_success = True

    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")
    report = {
        "repeated_intent_success_version": REPEATED_INTENT_SUCCESS_VERSION,
        "method": REPEATED_INTENT_SUCCESS_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "confidence_level": CONFIDENCE_LEVEL,
        "min_observable_trials": min_observable_trials,
        "min_sessions": min_sessions,
        "declared_profile": {
            "robot_id": identity["robot_id"],
            "embodiment_id": embodiment["embodiment_id"],
        },
        "observed_subject": {
            "series_id": series["series_id"],
            "robot_id": series["robot_id"],
            "embodiment_id": series["embodiment_id"],
        },
        "total_session_count": len(sessions),
        "total_trial_count": total_trial_count,
        "status": status,
        "evaluation_success": evaluation_success,
        "required_failures": required_failures,
        "required_inconclusive": required_inconclusive,
        "nonblocking_failures": nonblocking_failures,
        "nonblocking_inconclusive": nonblocking_inconclusive,
        "session_results": session_outputs,
        "intent_summaries": intent_summaries,
        "disclaimer": (
            "Repeated Intent Success v0.1 summarizes repeated observed satisfaction of declared engineering success conditions. "
            "It does not define a universal reliability threshold, measure source-motion similarity, prove causality or subjective motivation, or certify physical/functional safety."
        ),
    }
    validate_schema(report, "repeated-intent-success-report")
    return report
