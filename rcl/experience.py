from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from statistics import stdev
from typing import Any

from .profile import RCLValidationError, validate_schema


EXPERIENCE_VERSION = "0.1"
EXPERIENCE_SUMMARY_VERSION = "0.1"
EXPERIENCE_COMPACTION_METHOD = "rcl.experience.compaction.semantic_groups.v0.1"
DEFAULT_RETAINED_EXEMPLARS = 4


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if parsed.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return parsed


def _outcome_type(value: Any) -> str:
    if isinstance(value, bool):
        return "binary"
    if isinstance(value, (int, float)):
        return "numeric"
    raise RCLValidationError(f"Unsupported experience outcome value type: {type(value).__name__}")


def _round(value: float) -> float:
    return round(float(value), 6)


def _group_material(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": episode["context"],
        "action_id": episode["action"]["action_id"],
        "outcome_ids": sorted(episode["outcomes"]),
    }


def _group_key(episode: dict[str, Any]) -> str:
    return _canonical_json(_group_material(episode))


def _validate_cross_fields(store: dict[str, Any]) -> None:
    seen: set[str] = set()
    for episode in store["episodes"]:
        episode_id = episode["episode_id"]
        if episode_id in seen:
            raise RCLValidationError(f"Duplicate experience episode_id: {episode_id}")
        seen.add(episode_id)
        _parse_datetime(episode["observed_at"], label=episode_id)


def _numeric_summary(values: list[float]) -> dict[str, Any]:
    return {
        "type": "numeric",
        "count": len(values),
        "mean": _round(sum(values) / len(values)),
        "sample_std": None if len(values) < 2 else _round(stdev(values)),
        "min": _round(min(values)),
        "max": _round(max(values)),
    }


def _binary_summary(values: list[bool]) -> dict[str, Any]:
    true_count = sum(1 for value in values if value)
    false_count = len(values) - true_count
    return {
        "type": "binary",
        "count": len(values),
        "true_count": true_count,
        "false_count": false_count,
        "true_rate": _round(true_count / len(values)),
    }


def _summarize_outcomes(
    episodes: list[dict[str, Any]],
    outcome_ids: list[str],
    *,
    action_id: str,
) -> dict[str, Any]:
    if not episodes:
        return {}

    summaries: dict[str, Any] = {}
    for outcome_id in outcome_ids:
        values = [episode["outcomes"][outcome_id] for episode in episodes]
        types = {_outcome_type(value) for value in values}
        if len(types) != 1:
            raise RCLValidationError(
                f"Experience group {action_id} outcome {outcome_id!r} mixes types: {sorted(types)}"
            )
        outcome_type = next(iter(types))
        if outcome_type == "binary":
            summaries[outcome_id] = _binary_summary(values)
        else:
            summaries[outcome_id] = _numeric_summary([float(value) for value in values])
    return summaries


def _select_exemplars(episodes: list[dict[str, Any]], max_exemplars: int) -> list[str]:
    if max_exemplars <= 0:
        return []
    ordered = sorted(
        episodes,
        key=lambda item: (_parse_datetime(item["observed_at"], label=item["episode_id"]), item["episode_id"]),
    )
    if len(ordered) <= max_exemplars:
        return [item["episode_id"] for item in ordered]

    # Preserve both early and late examples so the summary retains longitudinal anchors.
    early_count = (max_exemplars + 1) // 2
    late_count = max_exemplars - early_count
    selected = ordered[:early_count]
    if late_count:
        selected += ordered[-late_count:]
    return [item["episode_id"] for item in selected]


def compact_experience(
    store: dict[str, Any],
    *,
    created_at: str | None = None,
    retained_exemplars: int = DEFAULT_RETAINED_EXEMPLARS,
) -> dict[str, Any]:
    """Create a deterministic, non-destructive semantic summary of experience episodes.

    Grouping is generic: exact semantic context + action ID + outcome-key set.
    The combined outcome summary is retained for backward compatibility, while
    action-stratified present/absent summaries preserve the association evidence
    needed by summary-aware Intent Discovery without reconstructing fake episodes.
    No behavior-specific rules, model training, raw-media ingestion, or source deletion occurs.
    """

    validate_schema(store, "experience-episode-set")
    _validate_cross_fields(store)
    if retained_exemplars < 0:
        raise RCLValidationError("retained_exemplars must be >= 0")

    source_copy = copy.deepcopy(store)
    source_digest = _sha256_text(_canonical_json(store))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for episode in store["episodes"]:
        grouped.setdefault(_group_key(episode), []).append(episode)

    groups: list[dict[str, Any]] = []
    for key in sorted(grouped):
        episodes = grouped[key]
        material = _group_material(episodes[0])
        ordered = sorted(
            episodes,
            key=lambda item: (_parse_datetime(item["observed_at"], label=item["episode_id"]), item["episode_id"]),
        )
        outcome_ids = material["outcome_ids"]
        present_episodes = [item for item in episodes if item["action"]["performed"]]
        absent_episodes = [item for item in episodes if not item["action"]["performed"]]

        outcome_summaries = _summarize_outcomes(
            episodes,
            outcome_ids,
            action_id=material["action_id"],
        )
        present_summaries = _summarize_outcomes(
            present_episodes,
            outcome_ids,
            action_id=material["action_id"],
        )
        absent_summaries = _summarize_outcomes(
            absent_episodes,
            outcome_ids,
            action_id=material["action_id"],
        )

        episode_ids = sorted(item["episode_id"] for item in episodes)
        group_digest = _sha256_text("\n".join(episode_ids))
        group_id = "experience-group-" + _sha256_text(key)[:16]
        groups.append(
            {
                "group_id": group_id,
                "context": material["context"],
                "action_id": material["action_id"],
                "outcome_ids": outcome_ids,
                "first_observed_at": ordered[0]["observed_at"],
                "last_observed_at": ordered[-1]["observed_at"],
                "episode_count": len(episodes),
                "action_present_count": len(present_episodes),
                "action_absent_count": len(absent_episodes),
                "outcomes": outcome_summaries,
                "action_strata": {
                    "present": {
                        "episode_count": len(present_episodes),
                        "outcomes": present_summaries,
                    },
                    "absent": {
                        "episode_count": len(absent_episodes),
                        "outcomes": absent_summaries,
                    },
                },
                "provenance": {
                    "source_episode_count": len(episodes),
                    "source_episode_id_digest_sha256": group_digest,
                    "retained_exemplar_episode_ids": _select_exemplars(episodes, retained_exemplars),
                },
            }
        )

    summary_material = {
        "store_id": store["store_id"],
        "source_digest_sha256": source_digest,
        "groups": groups,
    }
    summary = {
        "summary_version": EXPERIENCE_SUMMARY_VERSION,
        "method": EXPERIENCE_COMPACTION_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "summary_id": "experience-summary-" + _sha256_text(_canonical_json(summary_material))[:16],
        "source": {
            "store_id": store["store_id"],
            "episode_count": len(store["episodes"]),
            "source_digest_sha256": source_digest,
        },
        "group_count": len(groups),
        "groups": groups,
        "destructive": False,
    }
    validate_schema(summary, "experience-summary")

    if store != source_copy:
        raise RuntimeError("Experience compaction mutated its source input")
    return summary
