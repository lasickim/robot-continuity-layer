from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any

from .profile import RCLProfile, RCLValidationError, validate_schema


HABIT_PROMOTION_VERSION = "0.1"
HABIT_PROMOTION_METHOD = "rcl.habit.promotion.review.v0.1"
DEFAULT_POLICY_RESOURCE = "habit-promotion-policy-v0.1.json"

_TRANSITIONS = {
    "configured": ("configured_to_learning", "learning"),
    "learning": ("learning_to_stable", "stable"),
    "stable": ("stable_to_legacy", "legacy"),
}


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc


def _days_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 86400.0


def load_default_habit_promotion_policy() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", DEFAULT_POLICY_RESOURCE)
    policy = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(policy, "habit-promotion-policy")
    return policy


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


def _behavior_metrics(
    session_report: dict[str, Any],
    behavior_id: str,
    evidence_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metrics = [
        item
        for item in session_report["metric_summaries"]
        if item["behavior_id"] == behavior_id
    ]
    qualifying: list[dict[str, Any]] = []
    min_sessions = int(evidence_policy["min_scorable_sessions"])
    min_similarity = float(evidence_policy["min_metric_mean_similarity"])
    max_ci_half_width = float(evidence_policy["max_metric_ci_half_width"])

    for item in metrics:
        ci = item["confidence_interval_95"]
        if (
            int(item["session_count"]) >= min_sessions
            and float(item["mean_similarity"]) >= min_similarity
            and ci is not None
            and float(ci["half_width"]) <= max_ci_half_width
        ):
            qualifying.append(item)
    return metrics, qualifying


def _evidence_gates(
    session_report: dict[str, Any],
    behavior_id: str,
    evidence_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, int]:
    gates: list[dict[str, Any]] = []
    evaluation_success = bool(session_report["evaluation_success"])
    require_success = bool(evidence_policy["require_evaluation_success"])
    gates.append(
        _gate(
            "session_evaluation_success",
            actual=evaluation_success,
            required=require_success,
            passed=(evaluation_success or not require_success),
            reason="Repeated-session evidence must satisfy its own success policy when required.",
        )
    )

    status = session_report["status"]
    gates.append(
        _gate(
            "session_report_status",
            actual=status,
            required="estimated",
            passed=status == "estimated",
            reason="Promotion evidence must come from an estimated, comparable session series.",
        )
    )

    session_count = int(session_report["scorable_session_count"])
    min_sessions = int(evidence_policy["min_scorable_sessions"])
    gates.append(
        _gate(
            "scorable_sessions",
            actual=session_count,
            required={"minimum": min_sessions},
            passed=session_count >= min_sessions,
            reason="Enough comparable session-level observations must be available.",
        )
    )

    mean_score = session_report["mean_score"]
    min_mean_score = float(evidence_policy["min_mean_score"])
    gates.append(
        _gate(
            "mean_continuity_score",
            actual=mean_score,
            required={"minimum": min_mean_score},
            passed=mean_score is not None and float(mean_score) >= min_mean_score,
            reason="Repeated-session continuity must remain above the declared policy floor.",
        )
    )

    score_std = session_report["score_std"]
    max_score_std = float(evidence_policy["max_score_std"])
    gates.append(
        _gate(
            "between_session_std",
            actual=score_std,
            required={"maximum": max_score_std},
            passed=score_std is not None and float(score_std) <= max_score_std,
            reason="Large session-to-session variation blocks promotion review.",
        )
    )

    score_ci = session_report["confidence_interval_95"]
    score_ci_half_width = None if score_ci is None else float(score_ci["half_width"])
    max_score_ci_half_width = float(evidence_policy["max_score_ci_half_width"])
    gates.append(
        _gate(
            "score_ci_half_width",
            actual=score_ci_half_width,
            required={"maximum": max_score_ci_half_width},
            passed=(
                score_ci_half_width is not None
                and score_ci_half_width <= max_score_ci_half_width
            ),
            reason="Uncertainty around the repeated-session mean must be sufficiently narrow.",
        )
    )

    metrics, qualifying = _behavior_metrics(session_report, behavior_id, evidence_policy)
    min_metric_count = int(evidence_policy["min_behavior_metric_count"])
    gates.append(
        _gate(
            "qualifying_behavior_metrics",
            actual=len(qualifying),
            required={"minimum": min_metric_count},
            passed=len(qualifying) >= min_metric_count,
            reason="The candidate behavior itself must have enough stable metric evidence; overall score alone is insufficient.",
        )
    )
    return gates, len(metrics), len(qualifying)


def evaluate_habit_promotion_candidates(
    profile: RCLProfile,
    session_report: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    as_of: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate non-mutating lifecycle promotion recommendations.

    Habit history provides formation evidence. Repeated-session continuity is used
    only as supporting evidence that the declared behavior can be reproduced
    consistently; it is not direct proof that the original habit formed by itself.
    """

    validate_schema(session_report, "session-evaluation-report")
    policy_payload = policy or load_default_habit_promotion_policy()
    validate_schema(policy_payload, "habit-promotion-policy")

    behavior_payload = profile.load("behavior.json")
    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")

    as_of_value = as_of or session_report["created_at"]
    as_of_dt = _parse_datetime(as_of_value, label="as_of")
    created_at_value = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    decisions: list[dict[str, Any]] = []
    eligible_count = 0
    blocked_count = 0
    terminal_count = 0

    for behavior in behavior_payload["behaviors"]:
        habit = behavior.get("habit")
        if habit is None:
            continue

        behavior_id = behavior["behavior_id"]
        lifecycle = habit["lifecycle"]
        transition = _TRANSITIONS.get(lifecycle)
        if transition is None:
            terminal_count += 1
            decisions.append(
                {
                    "behavior_id": behavior_id,
                    "current_lifecycle": lifecycle,
                    "recommended_lifecycle": None,
                    "decision": "terminal",
                    "eligible": False,
                    "gates": [],
                    "behavior_metric_count": 0,
                    "qualifying_metric_count": 0,
                }
            )
            continue

        transition_key, recommended_lifecycle = transition
        transition_policy = policy_payload["transitions"][transition_key]
        gates: list[dict[str, Any]] = []

        source = behavior.get("source")
        allowed_sources = list(transition_policy["allowed_sources"])
        gates.append(
            _gate(
                "behavior_source",
                actual=source,
                required={"one_of": allowed_sources},
                passed=source in allowed_sources,
                reason="Only explicitly allowed behavior origins can use this promotion transition.",
            )
        )

        confidence = behavior.get("confidence")
        min_confidence = float(transition_policy["min_confidence"])
        gates.append(
            _gate(
                "behavior_confidence",
                actual=confidence,
                required={"minimum": min_confidence},
                passed=confidence is not None and float(confidence) >= min_confidence,
                reason="Behavior confidence must meet the versioned promotion policy threshold.",
            )
        )

        event_count = len(habit.get("events", []))
        min_history_events = int(transition_policy["min_history_events"])
        gates.append(
            _gate(
                "history_events",
                actual=event_count,
                required={"minimum": min_history_events},
                passed=event_count >= min_history_events,
                reason="Promotion review requires enough auditable habit-history events.",
            )
        )

        if transition_key in {"configured_to_learning", "learning_to_stable"}:
            first_observed = _parse_datetime(
                habit["first_observed_at"],
                label=f"{behavior_id}.habit.first_observed_at",
            )
            observation_days = _days_between(first_observed, as_of_dt)
            min_observation_days = float(transition_policy["min_observation_days"])
            gates.append(
                _gate(
                    "observation_age_days",
                    actual=round(observation_days, 6),
                    required={"minimum": min_observation_days},
                    passed=observation_days >= min_observation_days,
                    reason="The pattern must remain under observation long enough before promotion review.",
                )
            )
        else:
            stable_since_value = habit.get("stable_since")
            stable_since = (
                _parse_datetime(
                    stable_since_value,
                    label=f"{behavior_id}.habit.stable_since",
                )
                if stable_since_value is not None
                else None
            )
            stable_days = None if stable_since is None else _days_between(stable_since, as_of_dt)
            min_stable_days = float(transition_policy["min_stable_days"])
            gates.append(
                _gate(
                    "stable_age_days",
                    actual=None if stable_days is None else round(stable_days, 6),
                    required={"minimum": min_stable_days},
                    passed=stable_days is not None and stable_days >= min_stable_days,
                    reason="Legacy review requires a long-lived stable habit, not a recently stabilized one.",
                )
            )
            require_confirmation = bool(transition_policy["require_user_confirmation"])
            confirmed = habit.get("user_confirmed_at") is not None
            gates.append(
                _gate(
                    "user_confirmation",
                    actual=confirmed,
                    required=require_confirmation,
                    passed=confirmed or not require_confirmation,
                    reason="Legacy promotion may require explicit user confirmation under the selected policy.",
                )
            )

        behavior_metric_count = 0
        qualifying_metric_count = 0
        if "evidence" in transition_policy:
            evidence_gates, behavior_metric_count, qualifying_metric_count = _evidence_gates(
                session_report,
                behavior_id,
                transition_policy["evidence"],
            )
            gates.extend(evidence_gates)

        eligible = all(item["passed"] for item in gates)
        if eligible:
            eligible_count += 1
            decision = "candidate"
        else:
            blocked_count += 1
            decision = "blocked"

        decisions.append(
            {
                "behavior_id": behavior_id,
                "current_lifecycle": lifecycle,
                "recommended_lifecycle": recommended_lifecycle,
                "decision": decision,
                "eligible": eligible,
                "gates": gates,
                "behavior_metric_count": behavior_metric_count,
                "qualifying_metric_count": qualifying_metric_count,
            }
        )

    score_ci = session_report["confidence_interval_95"]
    report = {
        "promotion_version": HABIT_PROMOTION_VERSION,
        "method": HABIT_PROMOTION_METHOD,
        "created_at": created_at_value,
        "as_of": as_of_value,
        "policy": {
            "policy_id": policy_payload["policy_id"],
            "policy_version": policy_payload["policy_version"],
        },
        "profile": {
            "robot_id": identity["robot_id"],
            "continuity_generation": identity["continuity_generation"],
            "embodiment_id": embodiment["embodiment_id"],
        },
        "evidence_report": {
            "method": session_report["method"],
            "created_at": session_report["created_at"],
            "status": session_report["status"],
            "evaluation_success": session_report["evaluation_success"],
            "scorable_session_count": session_report["scorable_session_count"],
            "mean_score": session_report["mean_score"],
            "score_std": session_report["score_std"],
            "score_ci_half_width": None if score_ci is None else score_ci["half_width"],
        },
        "eligible_count": eligible_count,
        "blocked_count": blocked_count,
        "terminal_count": terminal_count,
        "decisions": decisions,
        "disclaimer": (
            "Habit promotion output is a non-mutating engineering review recommendation. "
            "Habit history supplies formation evidence; repeated-session continuity is supporting reproducibility evidence only. "
            "A candidate does not prove identity, consciousness, safety, user consent, or autonomous learning."
        ),
    }
    validate_schema(report, "habit-promotion-report")
    return report
