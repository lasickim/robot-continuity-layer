import copy
import json
from pathlib import Path

import pytest

from rcl.profile import RCLValidationError, validate_schema
from rcl.provenance_privacy import (
    PROVENANCE_EVALUATION_METHOD,
    PROVENANCE_PRIVACY_VERSION,
    artifact_sha256,
    create_artifact_provenance_record,
    evaluate_artifact_governance,
    load_default_provenance_privacy_policy,
    provenance_record_sha256,
    validate_artifact_provenance_record,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FIXTURE = ROOT / "examples" / "governance" / "public-artifact.json"
PRIVATE_FIXTURE = ROOT / "examples" / "governance" / "private-source.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _public_record(artifact):
    return create_artifact_provenance_record(
        artifact,
        artifact_id="public-note-001",
        artifact_type="documentation.note",
        created_at="2026-08-16T00:00:00Z",
        created_by="maintainer@example.org",
        origin_kind="operator",
        classification="public",
        sharing_scope="public",
        source_ref="repo://examples/governance/public-artifact.json",
        evidence_ref_propagation="public",
        evidence_content_copy="deployment_permitted",
    )


def _private_record(artifact):
    return create_artifact_provenance_record(
        artifact,
        artifact_id="private-source-001",
        artifact_type="experience.semantic_excerpt",
        created_at="2026-08-16T00:00:00Z",
        created_by="robot-runtime",
        origin_kind="sensor",
        classification="private",
        sharing_scope="approved_recipients",
        source_ref="sensor://semantic-experience/private-source-001",
        evidence_ref_propagation="approved_recipients",
        evidence_content_copy="not_permitted",
    )


def test_default_policy_is_schema_valid_and_conservative():
    policy = load_default_provenance_privacy_policy()
    validate_schema(policy, "provenance-privacy-policy")
    assert policy["privacy_order"] == ["public", "internal", "private", "restricted"]
    assert policy["automatic_declassification"] is False
    assert policy["content_privacy_inference"] is False
    assert policy["non_mutating"] is True


def test_public_artifact_can_be_publicly_shared_without_mutation():
    artifact = _load(PUBLIC_FIXTURE)
    artifact_before = copy.deepcopy(artifact)
    record = _public_record(artifact)
    record_before = copy.deepcopy(record)

    report = evaluate_artifact_governance(
        artifact,
        record,
        operation="share_public",
        include_external_evidence_refs=True,
        created_at="2026-08-16T00:05:00Z",
    )

    validate_schema(record, "artifact-provenance-record")
    validate_schema(report, "artifact-governance-report")
    assert artifact == artifact_before
    assert record == record_before
    assert report["report_version"] == PROVENANCE_PRIVACY_VERSION == "0.1"
    assert report["method"] == PROVENANCE_EVALUATION_METHOD
    assert report["status"] == "allowed"
    assert report["allowed"] is True
    assert report["non_mutating"] is True
    assert report["share_executed"] is False
    assert report["content_privacy_inferred"] is False


def test_private_artifact_is_blocked_from_public_share_but_allowed_for_approved_recipients():
    artifact = _load(PRIVATE_FIXTURE)
    record = _private_record(artifact)

    approved = evaluate_artifact_governance(
        artifact,
        record,
        operation="share_approved",
        include_external_evidence_refs=True,
        created_at="2026-08-16T00:05:00Z",
    )
    assert approved["status"] == "allowed"

    public = evaluate_artifact_governance(
        artifact,
        record,
        operation="share_public",
        created_at="2026-08-16T00:05:00Z",
    )
    assert public["status"] == "blocked"
    failed = {item["gate"] for item in public["gates"] if not item["passed"]}
    assert "privacy_classification" in failed
    assert "sharing_scope" in failed


def test_aggregation_does_not_automatically_declassify_or_expand_scope():
    source = _load(PRIVATE_FIXTURE)
    parent = _private_record(source)
    summary = {"source_count": 2, "completed_count": 2, "completion_rate": 1.0}

    with pytest.raises(RCLValidationError, match="automatic declassification"):
        create_artifact_provenance_record(
            summary,
            artifact_id="private-summary-001",
            artifact_type="experience.summary",
            created_at="2026-08-16T00:10:00Z",
            created_by="compactor",
            origin_kind="derived",
            classification="public",
            sharing_scope="approved_recipients",
            parent_records=[parent],
            parent_relationship="summarized_from",
            transformation_method="rcl.experience.compaction.demo",
            transformation_version="0.1",
            evidence_ref_propagation="approved_recipients",
        )

    with pytest.raises(RCLValidationError, match="sharing scope"):
        create_artifact_provenance_record(
            summary,
            artifact_id="private-summary-001",
            artifact_type="experience.summary",
            created_at="2026-08-16T00:10:00Z",
            created_by="compactor",
            origin_kind="derived",
            classification="private",
            sharing_scope="public",
            parent_records=[parent],
            parent_relationship="summarized_from",
            transformation_method="rcl.experience.compaction.demo",
            transformation_version="0.1",
            evidence_ref_propagation="approved_recipients",
        )


def test_valid_derived_record_binds_exact_parent_lineage():
    source = _load(PRIVATE_FIXTURE)
    parent = _private_record(source)
    summary = {"source_count": 2, "completed_count": 2, "completion_rate": 1.0}
    child = create_artifact_provenance_record(
        summary,
        artifact_id="private-summary-001",
        artifact_type="experience.summary",
        created_at="2026-08-16T00:10:00Z",
        created_by="compactor",
        origin_kind="derived",
        classification="private",
        sharing_scope="approved_recipients",
        parent_records=[parent],
        parent_relationship="summarized_from",
        transformation_method="rcl.experience.compaction.demo",
        transformation_version="0.1",
        evidence_ref_propagation="approved_recipients",
        evidence_content_copy="not_permitted",
    )

    assert child["parents"][0]["record_id"] == parent["record_id"]
    assert child["parents"][0]["record_sha256"] == provenance_record_sha256(parent)
    assert child["parents"][0]["artifact_sha256"] == artifact_sha256(source)
    validate_artifact_provenance_record(child, artifact=summary, parent_records=[parent])

    report = evaluate_artifact_governance(
        summary,
        child,
        operation="share_approved",
        parent_records=[parent],
        created_at="2026-08-16T00:15:00Z",
    )
    assert report["status"] == "allowed"
    assert report["provenance_record"]["parent_count"] == 1


def test_tampered_parent_record_is_rejected():
    source = _load(PRIVATE_FIXTURE)
    parent = _private_record(source)
    summary = {"source_count": 2}
    child = create_artifact_provenance_record(
        summary,
        artifact_id="summary-001",
        artifact_type="experience.summary",
        created_at="2026-08-16T00:10:00Z",
        created_by="compactor",
        origin_kind="derived",
        classification="private",
        sharing_scope="approved_recipients",
        parent_records=[parent],
        transformation_method="demo.compaction",
        evidence_ref_propagation="approved_recipients",
    )
    tampered = copy.deepcopy(parent)
    tampered["privacy"]["classification"] = "public"

    with pytest.raises(RCLValidationError, match="record_id"):
        evaluate_artifact_governance(
            summary,
            child,
            operation="local_use",
            parent_records=[tampered],
            created_at="2026-08-16T00:15:00Z",
        )


def test_artifact_digest_binding_rejects_modified_artifact():
    artifact = _load(PUBLIC_FIXTURE)
    record = _public_record(artifact)
    changed = copy.deepcopy(artifact)
    changed["message"] = "modified after provenance record creation"

    with pytest.raises(RCLValidationError, match="supplied artifact"):
        evaluate_artifact_governance(
            changed,
            record,
            operation="local_use",
            created_at="2026-08-16T00:15:00Z",
        )


def test_external_evidence_reference_and_content_copy_permissions_are_explicit():
    artifact = _load(PRIVATE_FIXTURE)
    record = _private_record(artifact)

    allowed_reference = evaluate_artifact_governance(
        artifact,
        record,
        operation="share_approved",
        include_external_evidence_refs=True,
        created_at="2026-08-16T00:15:00Z",
    )
    assert allowed_reference["allowed"] is True

    blocked_copy = evaluate_artifact_governance(
        artifact,
        record,
        operation="share_approved",
        include_external_evidence_refs=True,
        copy_external_evidence_content=True,
        created_at="2026-08-16T00:15:00Z",
    )
    assert blocked_copy["allowed"] is False
    assert any(
        item["gate"] == "external_evidence_content_copy" and not item["passed"]
        for item in blocked_copy["gates"]
    )
    assert blocked_copy["share_executed"] is False


def test_derived_record_cannot_expand_external_evidence_permissions():
    source = _load(PRIVATE_FIXTURE)
    parent = _private_record(source)
    summary = {"source_count": 2}

    with pytest.raises(RCLValidationError, match="evidence-ref propagation"):
        create_artifact_provenance_record(
            summary,
            artifact_id="summary-001",
            artifact_type="experience.summary",
            created_at="2026-08-16T00:10:00Z",
            created_by="compactor",
            origin_kind="derived",
            classification="private",
            sharing_scope="approved_recipients",
            parent_records=[parent],
            transformation_method="demo.compaction",
            evidence_ref_propagation="public",
        )


def test_non_derived_record_cannot_claim_transformation_lineage():
    artifact = _load(PUBLIC_FIXTURE)
    parent = _public_record(artifact)
    with pytest.raises(RCLValidationError, match="Only derived"):
        create_artifact_provenance_record(
            artifact,
            artifact_id="bad-lineage",
            artifact_type="documentation.note",
            created_at="2026-08-16T00:20:00Z",
            created_by="operator",
            origin_kind="operator",
            classification="public",
            sharing_scope="public",
            parent_records=[parent],
            transformation_method="not.allowed",
        )


def test_runtime_and_public_schemas_match():
    for name in (
        "provenance-privacy-policy",
        "artifact-provenance-record",
        "artifact-governance-report",
    ):
        runtime = json.loads((ROOT / "rcl" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert runtime == public


def test_runtime_and_public_default_policy_match():
    runtime = json.loads((ROOT / "rcl" / "data" / "provenance-privacy-policy-v0.1.json").read_text(encoding="utf-8"))
    public = json.loads((ROOT / "spec" / "policies" / "provenance-privacy-policy-v0.1.json").read_text(encoding="utf-8"))
    assert runtime == public
