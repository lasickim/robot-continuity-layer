from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any

from .experience import compact_experience
from .experience_retention import experience_store_sha256, verify_experience_summary_binding
from .profile import RCLValidationError, validate_schema


HABIT_EVIDENCE_VERSION = "0.1"
HABIT_EVIDENCE_METHOD = "rcl.habit.evidence.repeated_semantic_action.v0.1"
DEFAULT_HABIT_EVIDENCE_POLICY_RESOURCE = "habit-evidence-policy-v0.1.json"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if parsed.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return parsed


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_default_habit_evidence_policy() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", DEFAULT_HABIT_EVIDENCE_POLICY_RESOURCE)
    policy = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(policy, "habit-evidence-policy")
    return policy


def _matches_context(context: dict[str, Any], selector: dict[str, Any]) -> bool:
    return all(context.get(key) == value for key, value in selector.items())


def _validate_summary_self_binding(summary: dict[str, Any]) -> None:
    material = {
        "store_id": summary["source"]["store_id"],
        "source_digest_sha256": summary["source"]["source_digest_sha256"],
        "groups": summary["groups"],
    }
    expected = "experience-summary-" + _sha256_text(_canonical_json(material))[:16]
    if summary["summary_id"] != expected:
        raise RCLValidationError("Experience Summary summary_id does not match summary material")


def _group_view(group: dict[str, Any]) -> dict[str, Any]:
    count = int(group["episode_count"])
    present = int(group["action_present_count"])
    absent = int(group["action_absent_count"])
    return {
        "group_id": group["group_id"],
        "context": copy.deepcopy(group["context"]),
        "outcome_ids": list(group["outcome_ids"]),
        "episode_count": count,
        "action_present_count": present,
        "action_absent_count": absent,
        "repeat_rate": round(present / count, 6),
        "first_observed_at": group["first_observed_at"],
        "last_observed_at": group["last_observed_at"],
        "source_episode_id_digest_sha256": group["provenance"]["source_episode_id_digest_sha256"],
    }


def _metrics(groups: list[dict[str, Any]]) -> dict[str, Any]:
    if not groups:
        return {
            "matched_group_count": 0,
            "episode_count": 0,
            "action_present_count": 0,
            "action_absent_count": 0,
            "repeat_rate": None,
            "first_observed_at": None,
            "last_observed_at": None,
            "observation_span_days": None,
        }

    episode_count = sum(int(item["episode_count"]) for item in groups)
    present = sum(int(item["action_present_count"]) for item in groups)
    absent = sum(int(item["action_absent_count"]) for item in groups)
    first_item = min(
        groups,
        key=lambda item: _parse_datetime(item["first_observed_at"], label=item["group_id"]),
    )
    last_item = max(
        groups,
        key=lambda item: _parse_datetime(item["last_observed_at"], label=item["group_id"]),
    )
    first_dt = _parse_datetime(first_item["first_observed_at"], label="first_observed_at")
    last_dt = _parse_datetime(last_item["last_observed_at"], label="last_observed_at")
    span_days = (last_dt - first_dt).total_seconds() / 86400.0
    return {
        "matched_group_count": len(groups),
        "episode_count": episode_count,
        "action_present_count": present,
        "action_absent_count": absent,
        "repeat_rate": round(present / episode_count, 6),
        "first_observed_at": first_item["first_observed_at"],
        "last_observed_at": last_item["last_observed_at"],
        "observation_span_days": round(span_days, 6),
    }


def _gate(name: str, *, actual: Any, required: Any, passed: bool, reason: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "actual": actual,
        "required": required,
        "reason": reason,
    }


def _gates(metrics: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    repeat_rate = metrics["repeat_rate"]
    observation_span = metrics["observation_span_days"]
    return [
        _gate(
            "matched_semantic_groups",
            actual=metrics["matched_group_count"],
            required={"minimum": int(policy["min_matched_group_count"])},
            passed=metrics["matched_group_count"] >= int(policy["min_matched_group_count"]),
            reason="Habit review requires at least one semantic context group matching the behavior/action selector.",
        ),
        _gate(
            "episode_count",
            actual=metrics["episode_count"],
            required={"minimum": int(policy["min_episode_count"])},
            passed=metrics["episode_count"] >= int(policy["min_episode_count"]),
            reason="A repeated pattern needs enough observations before aggregate evidence is reviewable.",
        ),
        _gate(
            "action_present_count",
            actual=metrics["action_present_count"],
            required={"minimum": int(policy["min_action_present_count"])},
            passed=metrics["action_present_count"] >= int(policy["min_action_present_count"]),
            reason="The candidate action itself must have been observed enough times.",
        ),
        _gate(
            "repeat_rate",
            actual=repeat_rate,
            required={"minimum": float(policy["min_repeat_rate"])},
            passed=repeat_rate is not None and repeat_rate >= float(policy["min_repeat_rate"]),
            reason="The action must recur often enough inside the selected semantic context.",
        ),
        _gate(
            "observation_span_days",
            actual=observation_span,
            required={"minimum": float(policy["min_observation_span_days"])},
            passed=(
                observation_span is not None
                and observation_span >= float(policy["min_observation_span_days"])
            ),
            reason="Evidence should span enough time to avoid treating a short burst as a long-lived habit pattern.",
        ),
    ]


def _build_report(
    *,
    behavior_id: str,
    action_id: str,
    context_match: dict[str, Any],
    evidence_basis: str,
    source_verification: str,
    source: dict[str, Any],
    groups: list[dict[str, Any]],
    policy: dict[str, Any],
    created_at: str | None,
) -> dict[str, Any]:
    metrics = _metrics(groups)
    gates = _gates(metrics, policy)
    sufficient = all(item["passed"] for item in gates)
    report = {
        "habit_evidence_version": HABIT_EVIDENCE_VERSION,
        "method": HABIT_EVIDENCE_METHOD,
        "created_at": created_at or _utc_now_text(),
        "behavior_id": behavior_id,
        "action_id": action_id,
        "context_match": copy.deepcopy(context_match),
        "evidence_basis": evidence_basis,
        "source_verification": source_verification,
        "source": source,
        "metrics": metrics,
        "groups": groups,
        "gates": gates,
        "status": "sufficient" if sufficient else "insufficient",
        "supports_habit_review": sufficient,
        "pseudo_episodes_created": False,
        "non_mutating": True,
        "formation_claim": False,
        "disclaimer": (
            "Habit Evidence v0.1 measures repeated semantic action evidence only. "
            "Aggregate evidence remains aggregate, no pseudo-episodes are reconstructed, and a sufficient report does not itself promote a Habit lifecycle or prove subjective habit formation."
        ),
    }
    validate_schema(report, "habit-evidence-report")
    return report


def evaluate_habit_evidence_from_store(
    store: dict[str, Any],
    behavior_id: str,
    *,
    action_id: str | None = None,
    context_match: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate Habit formation-support evidence directly from raw Experience episodes."""

    source_before = copy.deepcopy(store)
    effective_policy = copy.deepcopy(policy or load_default_habit_evidence_policy())
    validate_schema(effective_policy, "habit-evidence-policy")
    selected_action = action_id or behavior_id
    selector = copy.deepcopy(context_match or {})

    # Compaction is reused only to obtain the canonical semantic group statistics.
    # The raw source remains authoritative and is not replaced by synthetic episodes.
    summary = compact_experience(store, retained_exemplars=0, created_at=created_at or _utc_now_text())
    matched_groups = [
        _group_view(group)
        for group in summary["groups"]
        if group["action_id"] == selected_action and _matches_context(group["context"], selector)
    ]
    matched_groups.sort(key=lambda item: item["group_id"])

    matched_ids = sorted(
        episode["episode_id"]
        for episode in store["episodes"]
        if episode["action"]["action_id"] == selected_action
        and _matches_context(episode["context"], selector)
    )
    source = {
        "store_id": store["store_id"],
        "source_digest_sha256": experience_store_sha256(store),
        "summary_id": None,
        "summary_sha256": None,
        "matched_episode_id_digest_sha256": _sha256_text("\n".join(matched_ids)),
    }
    report = _build_report(
        behavior_id=behavior_id,
        action_id=selected_action,
        context_match=selector,
        evidence_basis="raw",
        source_verification="direct_source",
        source=source,
        groups=matched_groups,
        policy=effective_policy,
        created_at=created_at,
    )
    if store != source_before:
        raise RuntimeError("Habit evidence evaluation mutated the raw Experience Store")
    return report


def evaluate_habit_evidence_from_summary(
    summary: dict[str, Any],
    behavior_id: str,
    *,
    action_id: str | None = None,
    context_match: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    source_store: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate Habit evidence from a compacted Experience Summary without pseudo-episodes."""

    summary_before = copy.deepcopy(summary)
    source_before = None if source_store is None else copy.deepcopy(source_store)
    validate_schema(summary, "experience-summary")
    _validate_summary_self_binding(summary)
    effective_policy = copy.deepcopy(policy or load_default_habit_evidence_policy())
    validate_schema(effective_policy, "habit-evidence-policy")
    selected_action = action_id or behavior_id
    selector = copy.deepcopy(context_match or {})

    verification = "summary_declared"
    if source_store is not None:
        verify_experience_summary_binding(source_store, summary)
        verification = "raw_verified"

    matched_groups = [
        _group_view(group)
        for group in summary["groups"]
        if group["action_id"] == selected_action and _matches_context(group["context"], selector)
    ]
    matched_groups.sort(key=lambda item: item["group_id"])
    source = {
        "store_id": summary["source"]["store_id"],
        "source_digest_sha256": summary["source"]["source_digest_sha256"],
        "summary_id": summary["summary_id"],
        "summary_sha256": _sha256_json(summary),
        "matched_episode_id_digest_sha256": None,
    }
    report = _build_report(
        behavior_id=behavior_id,
        action_id=selected_action,
        context_match=selector,
        evidence_basis="aggregate",
        source_verification=verification,
        source=source,
        groups=matched_groups,
        policy=effective_policy,
        created_at=created_at,
    )
    if summary != summary_before:
        raise RuntimeError("Habit evidence evaluation mutated the Experience Summary")
    if source_store is not None and source_store != source_before:
        raise RuntimeError("Habit evidence evaluation mutated the source Experience Store")
    return report
