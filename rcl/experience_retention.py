from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Iterable

from .experience import compact_experience
from .profile import RCLValidationError, validate_schema


EXPERIENCE_RETENTION_VERSION = "0.1"
EXPERIENCE_RETENTION_METHOD = "rcl.experience.retention.evaluate.v0.1"
EXPERIENCE_ARCHIVE_VERSION = "0.1"
EXPERIENCE_ARCHIVE_METHOD = "rcl.experience.archive.record.v0.1"
DEFAULT_EXPERIENCE_RETENTION_POLICY_RESOURCE = "experience-retention-policy-v0.1.json"


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


def load_default_experience_retention_policy() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", DEFAULT_EXPERIENCE_RETENTION_POLICY_RESOURCE)
    policy = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(policy, "experience-retention-policy")
    return policy


def experience_store_sha256(store: dict[str, Any]) -> str:
    validate_schema(store, "experience-episode-set")
    return _sha256_json(store)


def _group_material(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": episode["context"],
        "action_id": episode["action"]["action_id"],
        "outcome_ids": sorted(episode["outcomes"]),
    }


def _episode_group_id(episode: dict[str, Any]) -> str:
    key = _canonical_json(_group_material(episode))
    return "experience-group-" + _sha256_text(key)[:16]


def _group_membership(store: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for episode in store["episodes"]:
        groups.setdefault(_episode_group_id(episode), []).append(episode)
    return groups


def _expected_summary_id(summary: dict[str, Any]) -> str:
    material = {
        "store_id": summary["source"]["store_id"],
        "source_digest_sha256": summary["source"]["source_digest_sha256"],
        "groups": summary["groups"],
    }
    return "experience-summary-" + _sha256_text(_canonical_json(material))[:16]


def verify_experience_summary_binding(
    store: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Verify that a compaction summary is bound to this exact Experience Store.

    The check is deliberately stronger than matching only the top-level source
    digest. Group membership/counts, action strata, outcome summaries, source-ID
    digests, and exemplar membership are checked against the current source.
    """

    validate_schema(store, "experience-episode-set")
    validate_schema(summary, "experience-summary")

    # Reusing compaction validates cross-fields such as duplicate episode IDs,
    # timestamps, and mixed outcome types without mutating the source.
    expected = compact_experience(
        store,
        created_at=summary["created_at"],
        retained_exemplars=0,
    )
    source_digest = experience_store_sha256(store)

    if summary["source"]["store_id"] != store["store_id"]:
        raise RCLValidationError("Experience Summary store_id does not match source store")
    if summary["source"]["episode_count"] != len(store["episodes"]):
        raise RCLValidationError("Experience Summary episode_count does not match source store")
    if summary["source"]["source_digest_sha256"] != source_digest:
        raise RCLValidationError("Experience Summary source digest does not match source store")
    if summary["group_count"] != expected["group_count"]:
        raise RCLValidationError("Experience Summary group_count does not match source grouping")
    if summary["summary_id"] != _expected_summary_id(summary):
        raise RCLValidationError("Experience Summary summary_id does not match summary material")

    expected_by_id = {item["group_id"]: item for item in expected["groups"]}
    actual_by_id = {item["group_id"]: item for item in summary["groups"]}
    if len(actual_by_id) != len(summary["groups"]):
        raise RCLValidationError("Experience Summary contains duplicate group_id values")
    if set(actual_by_id) != set(expected_by_id):
        raise RCLValidationError("Experience Summary group IDs do not match source grouping")

    membership = _group_membership(store)
    for group_id in sorted(expected_by_id):
        expected_group = expected_by_id[group_id]
        actual_group = actual_by_id[group_id]
        for field in (
            "context",
            "action_id",
            "outcome_ids",
            "first_observed_at",
            "last_observed_at",
            "episode_count",
            "action_present_count",
            "action_absent_count",
            "outcomes",
            "action_strata",
        ):
            if actual_group.get(field) != expected_group.get(field):
                raise RCLValidationError(
                    f"{group_id}: Experience Summary {field} does not match source evidence"
                )

        actual_provenance = actual_group["provenance"]
        expected_provenance = expected_group["provenance"]
        for field in ("source_episode_count", "source_episode_id_digest_sha256"):
            if actual_provenance[field] != expected_provenance[field]:
                raise RCLValidationError(
                    f"{group_id}: Experience Summary provenance {field} does not match source evidence"
                )

        member_ids = {item["episode_id"] for item in membership[group_id]}
        exemplar_ids = actual_provenance["retained_exemplar_episode_ids"]
        if any(item not in member_ids for item in exemplar_ids):
            raise RCLValidationError(
                f"{group_id}: retained exemplar is not a member of the source semantic group"
            )

    return membership


def _archive_material(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "archived_at": record["archived_at"],
        "archived_by": record["archived_by"],
        "location_ref": record["location_ref"],
        "source": record["source"],
        "episode_ids": record["episode_ids"],
    }


def expected_experience_archive_id(record: dict[str, Any]) -> str:
    return "experience-archive-" + _sha256_json(_archive_material(record))[:16]


def create_experience_archive_record(
    store: dict[str, Any],
    episode_ids: Iterable[str],
    *,
    location_ref: str,
    archived_at: str,
    archived_by: str,
) -> dict[str, Any]:
    """Record a deployment assertion that selected episodes were archived.

    RCL does not perform the copy and does not inspect bytes at location_ref.
    The exact source store digest and episode IDs are bound into the record.
    """

    validate_schema(store, "experience-episode-set")
    # Validate source cross-fields through the existing compaction path.
    compact_experience(store, retained_exemplars=0)
    _parse_datetime(archived_at, label="archived_at")
    if not location_ref.strip():
        raise RCLValidationError("location_ref must be non-empty")
    if not archived_by.strip():
        raise RCLValidationError("archived_by must be non-empty")

    requested = list(episode_ids)
    if not requested:
        raise RCLValidationError("At least one episode_id is required for an archive record")
    if len(requested) != len(set(requested)):
        raise RCLValidationError("Archive record episode_ids must be unique")
    selected = sorted(requested)

    by_id = {item["episode_id"]: item for item in store["episodes"]}
    unknown = sorted(set(selected) - set(by_id))
    if unknown:
        raise RCLValidationError(f"Archive record references unknown episode IDs: {unknown}")

    archived_time = _parse_datetime(archived_at, label="archived_at")
    for episode_id in selected:
        observed = _parse_datetime(by_id[episode_id]["observed_at"], label=episode_id)
        if archived_time < observed:
            raise RCLValidationError(
                f"{episode_id}: archive timestamp cannot precede the episode observation"
            )

    record: dict[str, Any] = {
        "archive_version": EXPERIENCE_ARCHIVE_VERSION,
        "method": EXPERIENCE_ARCHIVE_METHOD,
        "archive_id": "",
        "archived_at": archived_at,
        "archived_by": archived_by,
        "location_ref": location_ref,
        "source": {
            "store_id": store["store_id"],
            "source_digest_sha256": experience_store_sha256(store),
        },
        "episode_count": len(selected),
        "episode_ids": selected,
        "episode_id_digest_sha256": _sha256_text("\n".join(selected)),
        "archive_assertion": "deployment_asserted_external_copy",
        "non_mutating": True,
        "archive_executed_by_rcl": False,
        "disclaimer": (
            "This archive record is a deployment assertion bound to the exact source-store digest and episode IDs. "
            "RCL did not copy, inspect, or verify bytes at the external location_ref and did not delete source data."
        ),
    }
    record["archive_id"] = expected_experience_archive_id(record)
    validate_schema(record, "experience-archive-record")
    return record


def validate_experience_archive_record(
    store: dict[str, Any],
    record: dict[str, Any],
) -> None:
    validate_schema(store, "experience-episode-set")
    validate_schema(record, "experience-archive-record")
    source_digest = experience_store_sha256(store)

    if record["source"]["store_id"] != store["store_id"]:
        raise RCLValidationError("Experience Archive Record store_id does not match source store")
    if record["source"]["source_digest_sha256"] != source_digest:
        raise RCLValidationError("Experience Archive Record is stale: source digest does not match")
    if record["archive_id"] != expected_experience_archive_id(record):
        raise RCLValidationError("Experience Archive Record archive_id does not match record material")
    if record["episode_count"] != len(record["episode_ids"]):
        raise RCLValidationError("Experience Archive Record episode_count does not match episode_ids")
    if record["episode_id_digest_sha256"] != _sha256_text("\n".join(record["episode_ids"])):
        raise RCLValidationError("Experience Archive Record episode ID digest does not match episode_ids")

    by_id = {item["episode_id"]: item for item in store["episodes"]}
    unknown = sorted(set(record["episode_ids"]) - set(by_id))
    if unknown:
        raise RCLValidationError(f"Experience Archive Record references unknown episodes: {unknown}")

    archived_time = _parse_datetime(record["archived_at"], label="archive_record.archived_at")
    for episode_id in record["episode_ids"]:
        observed = _parse_datetime(by_id[episode_id]["observed_at"], label=episode_id)
        if archived_time < observed:
            raise RCLValidationError(
                f"{episode_id}: archive record timestamp precedes the episode observation"
            )


def _archive_index(
    store: dict[str, Any],
    archive_records: Iterable[dict[str, Any]],
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    episode_to_records: dict[str, list[str]] = {}
    summaries: list[dict[str, Any]] = []
    seen_archive_ids: set[str] = set()
    for record in archive_records:
        validate_experience_archive_record(store, record)
        archive_id = record["archive_id"]
        if archive_id in seen_archive_ids:
            raise RCLValidationError(f"Duplicate Experience Archive Record: {archive_id}")
        seen_archive_ids.add(archive_id)
        for episode_id in record["episode_ids"]:
            episode_to_records.setdefault(episode_id, []).append(archive_id)
        summaries.append(
            {
                "archive_id": archive_id,
                "archive_record_sha256": _sha256_json(record),
                "episode_count": record["episode_count"],
                "location_ref": record["location_ref"],
            }
        )

    for values in episode_to_records.values():
        values.sort()
    summaries.sort(key=lambda item: item["archive_id"])
    return episode_to_records, summaries


def evaluate_experience_retention(
    store: dict[str, Any],
    summary: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    archive_records: Iterable[dict[str, Any]] = (),
    as_of: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Classify Experience episodes without deleting, moving, or mutating data."""

    source_before = copy.deepcopy(store)
    summary_before = copy.deepcopy(summary)
    archive_records_list = [copy.deepcopy(item) for item in archive_records]
    archive_records_before = copy.deepcopy(archive_records_list)

    effective_policy = copy.deepcopy(policy or load_default_experience_retention_policy())
    validate_schema(effective_policy, "experience-retention-policy")

    timestamp = created_at or _utc_now_text()
    as_of_text = as_of or timestamp
    _parse_datetime(timestamp, label="created_at")
    as_of_dt = _parse_datetime(as_of_text, label="as_of")

    membership = verify_experience_summary_binding(store, summary)
    episode_to_archive_ids, archive_record_summaries = _archive_index(
        store,
        archive_records_list,
    )

    summary_by_group = {item["group_id"]: item for item in summary["groups"]}
    decisions: list[dict[str, Any]] = []

    min_age = int(effective_policy["min_active_retention_days"])
    min_group_size = int(effective_policy["min_group_episode_count_for_prune"])
    max_fraction = float(effective_policy["max_prune_fraction_per_group"])
    protect_exemplars = bool(effective_policy["protect_retained_exemplars"])
    protect_refs = bool(effective_policy["protect_external_evidence_refs"])
    require_archive = bool(effective_policy["require_archive_record_for_prune"])

    for group_id in sorted(membership):
        episodes = sorted(
            membership[group_id],
            key=lambda item: (
                _parse_datetime(item["observed_at"], label=item["episode_id"]),
                item["episode_id"],
            ),
        )
        group_size = len(episodes)
        prune_limit = (
            math.floor(group_size * max_fraction)
            if group_size >= min_group_size
            else 0
        )
        exemplar_ids = set(
            summary_by_group[group_id]["provenance"]["retained_exemplar_episode_ids"]
        )

        staged: list[dict[str, Any]] = []
        prune_eligible: list[dict[str, Any]] = []

        for episode in episodes:
            episode_id = episode["episode_id"]
            observed_dt = _parse_datetime(episode["observed_at"], label=episode_id)
            delta_seconds = (as_of_dt - observed_dt).total_seconds()
            if delta_seconds < 0:
                raise RCLValidationError(
                    f"{episode_id}: as_of cannot precede the episode observation"
                )
            age_days = math.floor(delta_seconds / 86400)
            archive_ids = episode_to_archive_ids.get(episode_id, [])
            archived = bool(archive_ids)
            reasons: list[str] = []

            if age_days < min_age:
                reasons.append("within_active_retention_window")
            if protect_exemplars and episode_id in exemplar_ids:
                reasons.append("retained_summary_exemplar")
            if protect_refs and episode.get("evidence_refs"):
                reasons.append("external_evidence_reference")
            if group_size < min_group_size:
                reasons.append("sparse_semantic_group")

            base = {
                "episode_id": episode_id,
                "group_id": group_id,
                "observed_at": episode["observed_at"],
                "age_days": age_days,
                "group_episode_count": group_size,
                "group_prune_candidate_limit": prune_limit,
                "archived": archived,
                "archive_record_ids": archive_ids,
            }

            if reasons:
                staged.append(
                    {
                        **base,
                        "protected": True,
                        "decision": "retain",
                        "reasons": reasons,
                    }
                )
                continue

            candidate = {**base, "reasons": ["eligible_under_policy"]}
            if require_archive and not archived:
                staged.append(
                    {
                        **candidate,
                        "protected": False,
                        "decision": "archive_candidate",
                        "reasons": ["eligible_under_policy", "archive_record_required"],
                    }
                )
            else:
                prune_eligible.append(candidate)

        # Oldest eligible evidence is considered first. The per-group cap keeps
        # a deterministic active-store remainder even if every candidate was archived.
        for index, candidate in enumerate(prune_eligible):
            if index < prune_limit:
                reasons = list(candidate["reasons"])
                if candidate["archived"]:
                    reasons.append("archive_record_present")
                staged.append(
                    {
                        **candidate,
                        "protected": False,
                        "decision": "prune_candidate",
                        "reasons": reasons,
                    }
                )
            else:
                reasons = ["prune_fraction_guard"]
                if candidate["archived"]:
                    reasons.append("archive_record_present")
                staged.append(
                    {
                        **candidate,
                        "protected": True,
                        "decision": "retain",
                        "reasons": reasons,
                    }
                )

        decisions.extend(
            sorted(
                staged,
                key=lambda item: (
                    _parse_datetime(item["observed_at"], label=item["episode_id"]),
                    item["episode_id"],
                ),
            )
        )

    counts = {
        "total": len(decisions),
        "retain": sum(1 for item in decisions if item["decision"] == "retain"),
        "archive_candidate": sum(
            1 for item in decisions if item["decision"] == "archive_candidate"
        ),
        "prune_candidate": sum(
            1 for item in decisions if item["decision"] == "prune_candidate"
        ),
    }

    report = {
        "retention_version": EXPERIENCE_RETENTION_VERSION,
        "method": EXPERIENCE_RETENTION_METHOD,
        "created_at": timestamp,
        "as_of": as_of_text,
        "policy": {
            "policy_id": effective_policy["policy_id"],
            "policy_version": effective_policy["policy_version"],
        },
        "source": {
            "store_id": store["store_id"],
            "episode_count": len(store["episodes"]),
            "source_digest_sha256": experience_store_sha256(store),
        },
        "summary": {
            "summary_id": summary["summary_id"],
            "summary_sha256": _sha256_json(summary),
            "binding_verified": True,
        },
        "archive_records": archive_record_summaries,
        "counts": counts,
        "decisions": decisions,
        "non_mutating": True,
        "prune_executed": False,
        "archive_executed_by_rcl": False,
        "disclaimer": (
            "Experience Retention v0.1 classifies active-store lifecycle candidates only. "
            "Compaction is not deletion consent; prune_candidate does not delete data, and archive records are deployment assertions rather than RCL verification of remote bytes."
        ),
    }
    validate_schema(report, "experience-retention-report")

    if store != source_before:
        raise RuntimeError("Experience retention evaluation mutated the source store")
    if summary != summary_before:
        raise RuntimeError("Experience retention evaluation mutated the source summary")
    if archive_records_list != archive_records_before:
        raise RuntimeError("Experience retention evaluation mutated archive records")
    return report
