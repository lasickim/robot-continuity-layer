from __future__ import annotations

import argparse
import json
from pathlib import Path

from .provenance_privacy import (
    create_artifact_provenance_record,
    evaluate_artifact_governance,
)


def _read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_or_print(value, output: str | None, as_json: bool) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)
    elif as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def _record_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl record-artifact-provenance")
    parser.add_argument("artifact")
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--artifact-type", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--created-by", required=True)
    parser.add_argument("--origin-kind", required=True)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--sharing-scope", required=True)
    parser.add_argument("--source-ref")
    parser.add_argument("--parent-record", action="append", default=[])
    parser.add_argument("--parent-relationship", default="derived_from")
    parser.add_argument("--transformation-method")
    parser.add_argument("--transformation-version")
    parser.add_argument(
        "--evidence-ref-propagation",
        default="exclude",
        choices=["exclude", "approved_recipients", "public"],
    )
    parser.add_argument(
        "--evidence-content-copy",
        default="not_permitted",
        choices=["not_permitted", "deployment_permitted"],
    )
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run_record(argv: list[str]) -> int:
    args = _record_parser().parse_args(argv)
    artifact = _read_json(args.artifact)
    parents = [_read_json(path) for path in args.parent_record]
    record = create_artifact_provenance_record(
        artifact,
        artifact_id=args.artifact_id,
        artifact_type=args.artifact_type,
        created_at=args.created_at,
        created_by=args.created_by,
        origin_kind=args.origin_kind,
        classification=args.classification,
        sharing_scope=args.sharing_scope,
        source_ref=args.source_ref,
        parent_records=parents,
        parent_relationship=args.parent_relationship,
        transformation_method=args.transformation_method,
        transformation_version=args.transformation_version,
        evidence_ref_propagation=args.evidence_ref_propagation,
        evidence_content_copy=args.evidence_content_copy,
    )

    if args.output or args.json:
        _write_or_print(record, args.output, args.json)
    else:
        privacy = record["privacy"]
        print("RCL Artifact Provenance Record")
        print(f"Record: {record['record_id']}")
        print(f"Artifact: {record['artifact']['artifact_id']} [{record['artifact']['artifact_type']}]")
        print(f"Artifact SHA-256: {record['artifact']['sha256']}")
        print(f"Origin: {record['origin']['kind']}")
        print(f"Parents: {len(record['parents'])}")
        print(f"Privacy: {privacy['classification']}")
        print(f"Sharing Scope: {privacy['sharing_scope']}")
        print(f"Evidence Ref Propagation: {privacy['external_evidence_refs']['propagation']}")
        print(f"Evidence Content Copy: {privacy['external_evidence_refs']['content_copy']}")
        print("Content Privacy Inferred: NO")
        print("Artifact Mutated: NO")
    return 0


def _evaluate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl evaluate-artifact-governance")
    parser.add_argument("artifact")
    parser.add_argument("record")
    parser.add_argument(
        "--operation",
        required=True,
        choices=["local_use", "share_approved", "share_public", "archive", "prune_review"],
    )
    parser.add_argument("--parent-record", action="append", default=[])
    parser.add_argument("--include-evidence-refs", action="store_true")
    parser.add_argument("--copy-evidence-content", action="store_true")
    parser.add_argument("--policy")
    parser.add_argument("--created-at")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run_evaluate(argv: list[str]) -> int:
    args = _evaluate_parser().parse_args(argv)
    artifact = _read_json(args.artifact)
    record = _read_json(args.record)
    parents = [_read_json(path) for path in args.parent_record]
    policy = _read_json(args.policy) if args.policy else None
    report = evaluate_artifact_governance(
        artifact,
        record,
        operation=args.operation,
        parent_records=parents,
        include_external_evidence_refs=args.include_evidence_refs,
        copy_external_evidence_content=args.copy_evidence_content,
        policy=policy,
        created_at=args.created_at,
    )

    if args.output or args.json:
        _write_or_print(report, args.output, args.json)
    else:
        print("RCL Artifact Governance Review")
        print(f"Artifact: {report['artifact']['artifact_id']}")
        print(f"Operation: {report['operation']}")
        print(f"Privacy: {report['provenance_record']['privacy_classification']}")
        print(f"Sharing Scope: {report['provenance_record']['sharing_scope']}")
        print(f"Status: {report['status'].upper()}")
        for gate in report["gates"]:
            if not gate["passed"]:
                print(
                    f"- BLOCK {gate['gate']}: actual={gate['actual']!r} required={gate['required']!r}"
                )
        print("Content Privacy Inferred: NO")
        print("Share Executed: NO")
        print("Archive Executed: NO")
        print("Prune Executed: NO")
        print("Artifact Mutated: NO")
    return 0 if report["allowed"] else 7
