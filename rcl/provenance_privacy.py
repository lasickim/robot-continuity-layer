from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Iterable

from .profile import RCLValidationError, validate_schema


PROVENANCE_PRIVACY_VERSION = "0.1"
PROVENANCE_RECORD_METHOD = "rcl.provenance_privacy.record.v0.1"
PROVENANCE_EVALUATION_METHOD = "rcl.provenance_privacy.evaluate.v0.1"
DEFAULT_PROVENANCE_PRIVACY_POLICY_RESOURCE = "provenance-privacy-policy-v0.1.json"

PRIVACY_CLASSIFICATIONS = ("public", "internal", "private", "restricted")
SHARING_SCOPES = ("local_only", "approved_recipients", "public")
EVIDENCE_REF_PROPAGATION = ("exclude", "approved_recipients", "public")
ORIGIN_KINDS = ("sensor", "user", "operator", "imported", "model", "derived", "system", "other")
OPERATIONS = ("local_use", "share_approved", "share_public", "archive", "prune_review")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def artifact_sha256(artifact: Any) -> str:
    return _sha256_text(_canonical_json(artifact))


def provenance_record_sha256(record: dict[str, Any]) -> str:
    return _sha256_text(_canonical_json(record))


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if result.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return result


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_default_provenance_privacy_policy() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", DEFAULT_PROVENANCE_PRIVACY_POLICY_RESOURCE)
    policy = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(policy, "provenance-privacy-policy")
    return policy


def _record_material(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "record_id"}


def expected_provenance_record_id(record: dict[str, Any]) -> str:
    return "artifact-provenance-" + _sha256_text(_canonical_json(_record_material(record)))[:16]


def _rank(value: str, order: Iterable[str], *, label: str) -> int:
    values = tuple(order)
    try:
        return values.index(value)
    except ValueError as exc:
        raise RCLValidationError(f"Unknown {label}: {value}") from exc


def _validate_self_integrity(record: dict[str, Any]) -> None:
    validate_schema(record, "artifact-provenance-record")
    _parse_datetime(record["created_at"], label="provenance.created_at")
    if record["record_id"] != expected_provenance_record_id(record):
        raise RCLValidationError("Artifact Provenance Record record_id does not match record material")

    origin_kind = record["origin"]["kind"]
    has_parents = bool(record["parents"])
    has_transformation = "transformation" in record
    if origin_kind == "derived":
        if not has_parents:
            raise RCLValidationError("Derived provenance requires at least one parent record")
        if not has_transformation:
            raise RCLValidationError("Derived provenance requires transformation metadata")
    else:
        if has_parents:
            raise RCLValidationError("Non-derived provenance must not declare parent lineage in v0.1")
        if has_transformation:
            raise RCLValidationError("Non-derived provenance must not declare transformation metadata in v0.1")

    parent_ids = [item["record_id"] for item in record["parents"]]
    if len(parent_ids) != len(set(parent_ids)):
        raise RCLValidationError("Artifact Provenance Record contains duplicate parent record IDs")


def _parent_index(parent_records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for parent in parent_records:
        _validate_self_integrity(parent)
        record_id = parent["record_id"]
        if record_id in index:
            raise RCLValidationError(f"Duplicate supplied parent provenance record: {record_id}")
        index[record_id] = parent
    return index


def _validate_parent_lineage(
    record: dict[str, Any],
    parent_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    supplied = _parent_index(parent_records)
    declared_ids = [item["record_id"] for item in record["parents"]]
    if set(declared_ids) != set(supplied):
        raise RCLValidationError(
            "Supplied parent provenance records do not exactly match the child record lineage"
        )

    ordered: list[dict[str, Any]] = []
    for link in record["parents"]:
        parent = supplied[link["record_id"]]
        if link["record_sha256"] != provenance_record_sha256(parent):
            raise RCLValidationError(
                f"{link['record_id']}: parent record SHA-256 does not match supplied parent record"
            )
        if link["artifact_id"] != parent["artifact"]["artifact_id"]:
            raise RCLValidationError(
                f"{link['record_id']}: parent artifact_id does not match supplied parent record"
            )
        if link["artifact_sha256"] != parent["artifact"]["sha256"]:
            raise RCLValidationError(
                f"{link['record_id']}: parent artifact SHA-256 does not match supplied parent record"
            )
        ordered.append(parent)
    return ordered


def _validate_privacy_inheritance(
    record: dict[str, Any],
    parents: Iterable[dict[str, Any]],
    *,
    policy: dict[str, Any],
) -> None:
    parent_list = list(parents)
    if not parent_list:
        return

    privacy_order = policy["privacy_order"]
    sharing_order = policy["sharing_scope_order"]
    propagation_order = policy["evidence_ref_propagation_order"]

    child_privacy = record["privacy"]
    child_class_rank = _rank(child_privacy["classification"], privacy_order, label="privacy classification")
    max_parent_class_rank = max(
        _rank(item["privacy"]["classification"], privacy_order, label="privacy classification")
        for item in parent_list
    )
    if child_class_rank < max_parent_class_rank:
        raise RCLValidationError(
            "Derived artifact privacy classification is less restrictive than a parent; automatic declassification is forbidden"
        )

    child_scope_rank = _rank(child_privacy["sharing_scope"], sharing_order, label="sharing scope")
    most_restrictive_parent_scope = min(
        _rank(item["privacy"]["sharing_scope"], sharing_order, label="sharing scope")
        for item in parent_list
    )
    if child_scope_rank > most_restrictive_parent_scope:
        raise RCLValidationError(
            "Derived artifact sharing scope is broader than a parent; automatic scope expansion is forbidden"
        )

    child_propagation_rank = _rank(
        child_privacy["external_evidence_refs"]["propagation"],
        propagation_order,
        label="evidence-ref propagation",
    )
    most_restrictive_parent_propagation = min(
        _rank(
            item["privacy"]["external_evidence_refs"]["propagation"],
            propagation_order,
            label="evidence-ref propagation",
        )
        for item in parent_list
    )
    if child_propagation_rank > most_restrictive_parent_propagation:
        raise RCLValidationError(
            "Derived artifact evidence-ref propagation is broader than a parent"
        )

    if child_privacy["external_evidence_refs"]["content_copy"] == "deployment_permitted":
        if any(
            item["privacy"]["external_evidence_refs"]["content_copy"] != "deployment_permitted"
            for item in parent_list
        ):
            raise RCLValidationError(
                "Derived artifact cannot permit external evidence content copy when a parent forbids it"
            )


def validate_artifact_provenance_record(
    record: dict[str, Any],
    *,
    artifact: Any | None = None,
    parent_records: Iterable[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> None:
    """Validate record integrity, optional artifact binding, and optional resolved lineage."""

    effective_policy = copy.deepcopy(policy or load_default_provenance_privacy_policy())
    validate_schema(effective_policy, "provenance-privacy-policy")
    _validate_self_integrity(record)

    if artifact is not None and record["artifact"]["sha256"] != artifact_sha256(artifact):
        raise RCLValidationError("Artifact Provenance Record SHA-256 does not match supplied artifact")

    if parent_records is not None:
        parents = _validate_parent_lineage(record, parent_records)
        _validate_privacy_inheritance(record, parents, policy=effective_policy)


def create_artifact_provenance_record(
    artifact: Any,
    *,
    artifact_id: str,
    artifact_type: str,
    created_at: str,
    created_by: str,
    origin_kind: str,
    classification: str,
    sharing_scope: str,
    source_ref: str | None = None,
    parent_records: Iterable[dict[str, Any]] = (),
    parent_relationship: str = "derived_from",
    transformation_method: str | None = None,
    transformation_version: str | None = None,
    evidence_ref_propagation: str = "exclude",
    evidence_content_copy: str = "not_permitted",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a non-mutating provenance/privacy companion record for one JSON artifact."""

    effective_policy = copy.deepcopy(policy or load_default_provenance_privacy_policy())
    validate_schema(effective_policy, "provenance-privacy-policy")
    _parse_datetime(created_at, label="created_at")
    if not created_by.strip():
        raise RCLValidationError("created_by must be non-empty")
    if origin_kind not in ORIGIN_KINDS:
        raise RCLValidationError(f"Unsupported origin kind: {origin_kind}")
    if classification not in PRIVACY_CLASSIFICATIONS:
        raise RCLValidationError(f"Unsupported privacy classification: {classification}")
    if sharing_scope not in SHARING_SCOPES:
        raise RCLValidationError(f"Unsupported sharing scope: {sharing_scope}")
    if evidence_ref_propagation not in EVIDENCE_REF_PROPAGATION:
        raise RCLValidationError(f"Unsupported evidence-ref propagation: {evidence_ref_propagation}")
    if evidence_content_copy not in {"not_permitted", "deployment_permitted"}:
        raise RCLValidationError(f"Unsupported evidence content-copy declaration: {evidence_content_copy}")

    parents = [copy.deepcopy(item) for item in parent_records]
    parent_index = _parent_index(parents)
    if origin_kind == "derived" and not parents:
        raise RCLValidationError("Derived provenance requires parent_records")
    if origin_kind != "derived" and parents:
        raise RCLValidationError("Only derived provenance may declare parent_records in v0.1")
    if origin_kind == "derived" and not transformation_method:
        raise RCLValidationError("Derived provenance requires transformation_method")
    if origin_kind != "derived" and (transformation_method or transformation_version):
        raise RCLValidationError("Non-derived provenance must not declare transformation metadata")

    links = []
    for record_id in sorted(parent_index):
        parent = parent_index[record_id]
        links.append(
            {
                "record_id": record_id,
                "record_sha256": provenance_record_sha256(parent),
                "artifact_id": parent["artifact"]["artifact_id"],
                "artifact_sha256": parent["artifact"]["sha256"],
                "relationship": parent_relationship,
            }
        )

    record: dict[str, Any] = {
        "record_version": PROVENANCE_PRIVACY_VERSION,
        "method": PROVENANCE_RECORD_METHOD,
        "record_id": "",
        "created_at": created_at,
        "created_by": created_by,
        "artifact": {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "sha256": artifact_sha256(artifact),
        },
        "origin": {"kind": origin_kind},
        "parents": links,
        "privacy": {
            "classification": classification,
            "sharing_scope": sharing_scope,
            "external_evidence_refs": {
                "propagation": evidence_ref_propagation,
                "content_copy": evidence_content_copy,
            },
        },
        "non_mutating": True,
        "content_privacy_inferred": False,
        "disclaimer": (
            "This record binds declared provenance and privacy metadata to a canonical JSON artifact digest. "
            "RCL does not infer legal privacy status or consent from artifact contents and does not perform sharing, archival, or deletion."
        ),
    }
    if source_ref is not None:
        if not source_ref.strip():
            raise RCLValidationError("source_ref must be non-empty when supplied")
        record["origin"]["source_ref"] = source_ref
    if origin_kind == "derived":
        transformation: dict[str, Any] = {"method": transformation_method}
        if transformation_version is not None:
            if not transformation_version.strip():
                raise RCLValidationError("transformation_version must be non-empty when supplied")
            transformation["version"] = transformation_version
        record["transformation"] = transformation

    record["record_id"] = expected_provenance_record_id(record)
    validate_artifact_provenance_record(
        record,
        artifact=artifact,
        parent_records=parents,
        policy=effective_policy,
    )
    return record


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


def evaluate_artifact_governance(
    artifact: Any,
    record: dict[str, Any],
    *,
    operation: str,
    parent_records: Iterable[dict[str, Any]] = (),
    include_external_evidence_refs: bool = False,
    copy_external_evidence_content: bool = False,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Review one requested operation without executing any I/O or mutation."""

    if operation not in OPERATIONS:
        raise RCLValidationError(f"Unsupported governance operation: {operation}")
    if copy_external_evidence_content and not include_external_evidence_refs:
        raise RCLValidationError(
            "copy_external_evidence_content requires include_external_evidence_refs=true"
        )

    effective_policy = copy.deepcopy(policy or load_default_provenance_privacy_policy())
    validate_schema(effective_policy, "provenance-privacy-policy")
    parents = [copy.deepcopy(item) for item in parent_records]
    validate_artifact_provenance_record(
        record,
        artifact=artifact,
        parent_records=parents,
        policy=effective_policy,
    )

    timestamp = created_at or _utc_now_text()
    _parse_datetime(timestamp, label="created_at")

    privacy = record["privacy"]
    operation_rule = effective_policy["operations"][operation]
    sharing_order = effective_policy["sharing_scope_order"]
    propagation_order = effective_policy["evidence_ref_propagation_order"]

    gates: list[dict[str, Any]] = []
    classification_allowed = privacy["classification"] in operation_rule["allowed_classifications"]
    gates.append(
        _gate(
            "privacy_classification",
            actual=privacy["classification"],
            required={"one_of": operation_rule["allowed_classifications"]},
            passed=classification_allowed,
            reason="The requested operation must be permitted for the declared privacy classification.",
        )
    )

    actual_scope_rank = _rank(privacy["sharing_scope"], sharing_order, label="sharing scope")
    required_scope = operation_rule["minimum_sharing_scope"]
    required_scope_rank = _rank(required_scope, sharing_order, label="sharing scope")
    scope_allowed = actual_scope_rank >= required_scope_rank
    gates.append(
        _gate(
            "sharing_scope",
            actual=privacy["sharing_scope"],
            required={"minimum": required_scope},
            passed=scope_allowed,
            reason="The declared sharing scope must be broad enough for the requested operation.",
        )
    )

    if include_external_evidence_refs:
        required_propagation: str | None = None
        if operation == "share_approved":
            required_propagation = effective_policy["external_evidence"]["share_approved_minimum_propagation"]
        elif operation == "share_public":
            required_propagation = effective_policy["external_evidence"]["share_public_minimum_propagation"]

        if required_propagation is not None:
            actual_propagation = privacy["external_evidence_refs"]["propagation"]
            actual_rank = _rank(
                actual_propagation,
                propagation_order,
                label="evidence-ref propagation",
            )
            required_rank = _rank(
                required_propagation,
                propagation_order,
                label="evidence-ref propagation",
            )
            gates.append(
                _gate(
                    "external_evidence_ref_propagation",
                    actual=actual_propagation,
                    required={"minimum": required_propagation},
                    passed=actual_rank >= required_rank,
                    reason="External evidence references require an explicit propagation scope for sharing.",
                )
            )

    if copy_external_evidence_content:
        copy_permission = privacy["external_evidence_refs"]["content_copy"]
        gates.append(
            _gate(
                "external_evidence_content_copy",
                actual=copy_permission,
                required="deployment_permitted",
                passed=copy_permission == "deployment_permitted",
                reason=(
                    "Copying externally managed evidence content requires an explicit deployment permission declaration; "
                    "RCL still does not execute the copy."
                ),
            )
        )

    allowed = all(item["passed"] for item in gates)
    report = {
        "report_version": PROVENANCE_PRIVACY_VERSION,
        "method": PROVENANCE_EVALUATION_METHOD,
        "created_at": timestamp,
        "artifact": copy.deepcopy(record["artifact"]),
        "provenance_record": {
            "record_id": record["record_id"],
            "record_sha256": provenance_record_sha256(record),
            "privacy_classification": privacy["classification"],
            "sharing_scope": privacy["sharing_scope"],
            "parent_count": len(record["parents"]),
        },
        "policy": {
            "policy_id": effective_policy["policy_id"],
            "policy_version": effective_policy["policy_version"],
        },
        "operation": operation,
        "include_external_evidence_refs": bool(include_external_evidence_refs),
        "copy_external_evidence_content": bool(copy_external_evidence_content),
        "status": "allowed" if allowed else "blocked",
        "allowed": allowed,
        "gates": gates,
        "non_mutating": True,
        "share_executed": False,
        "archive_executed": False,
        "prune_executed": False,
        "content_privacy_inferred": False,
        "disclaimer": (
            "This report is an engineering governance review, not legal/privacy compliance certification. "
            "No sharing, archival, pruning, external evidence copy, consent inference, or content-based privacy classification was executed."
        ),
    }
    validate_schema(report, "artifact-governance-report")
    return report
