import json
from pathlib import Path

from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.hil_reference import (
    build_hil_runtime_attestation,
    evaluate_hil_readiness,
    run_hil_reference_experiment,
)
from rcl.profile import RCLProfile, validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_args():
    base = _root() / "examples" / "v0.5-sim"
    return (
        RCLProfile.open(base / "robot-a"),
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _read(base / "robot-b.intent-series.json"),
    )


def test_unclassified_runtime_cannot_claim_hil():
    attestation = build_hil_runtime_attestation(component_id="ci-host", environment="ci")
    readiness = evaluate_hil_readiness(attestation)
    assert readiness["eligible"] is False

    profile, target, source_series, target_series = _fixture_args()
    report = run_hil_reference_experiment(
        profile,
        target,
        source_series,
        target_series,
        CapabilityPathReferenceAdapter(),
        attestation,
        behavior_id="safety.pre_sit_clearance_check",
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T07:00:00Z",
    )
    assert report["status"] == "not_eligible"
    assert report["evidence_grade"] == "UNCLASSIFIED"
    assert report["assertions"]["semantic_experiment_passed"] is True
    assert report["assertions"]["experiment_passed"] is False


def test_declared_deployment_boundary_is_contract_eligible():
    attestation = build_hil_runtime_attestation(
        component_id="edge-controller-01",
        environment="deployment",
        real_roles=("compute",),
        simulated_roles=("plant",),
        evidence_refs=("file://hil-run/runtime-log.json",),
        captured_at="2026-08-16T07:00:00Z",
    )
    readiness = evaluate_hil_readiness(attestation)
    assert readiness["eligible"] is True

    profile, target, source_series, target_series = _fixture_args()
    report = run_hil_reference_experiment(
        profile,
        target,
        source_series,
        target_series,
        CapabilityPathReferenceAdapter(),
        attestation,
        behavior_id="safety.pre_sit_clearance_check",
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T07:00:00Z",
    )
    validate_schema(report, "hil-reference-report")
    assert report["status"] == "passed"
    assert report["evidence_grade"] == "HIL"
    assert report["attestation"]["attestation_trust"] == "self_declared"
    assert report["assertions"]["experiment_passed"] is True


def test_hil_schemas_are_published_with_runtime_parity():
    root = _root()
    for name in ("hil-runtime-attestation", "hil-reference-report"):
        assert _read(root / "rcl" / "schemas" / f"{name}.schema.json") == _read(
            root / "spec" / "schemas" / f"{name}.schema.json"
        )
