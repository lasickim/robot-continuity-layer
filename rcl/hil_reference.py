from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from typing import Any

from .adapter import RCLAdapter
from .profile import RCLProfile, validate_schema
from .simulation_reference import run_simulation_reference_experiment


HIL_ATTESTATION_VERSION = "0.1"
HIL_REFERENCE_VERSION = "0.1"
HIL_REFERENCE_METHOD = "rcl.hil.reference_migration.v0.5"
_ALLOWED_REAL_ROLES = {"compute", "sensor", "controller"}
_ALLOWED_SIMULATED_ROLES = {"plant", "actuator", "environment", "sensor"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_hil_runtime_attestation(
    *,
    component_id: str,
    environment: str = "unclassified",
    real_roles: tuple[str, ...] = ("compute",),
    simulated_roles: tuple[str, ...] = ("plant",),
    evidence_refs: tuple[str, ...] = (),
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Build a self-declared runtime attestation for an HIL execution boundary.

    The function records runtime facts available to Python but does not claim
    cryptographic proof of hardware identity. Deployments remain responsible for
    preserving stronger external evidence when required.
    """

    attestation = {
        "hil_attestation_version": HIL_ATTESTATION_VERSION,
        "captured_at": captured_at or _now(),
        "attestation_trust": "self_declared",
        "environment": environment,
        "component_id": component_id,
        "runtime": {
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system() or "unknown",
            "machine": platform.machine() or "unknown",
            "executable": sys.executable,
        },
        "real_components": [
            {"role": role, "component_id": component_id} for role in real_roles
        ],
        "simulated_components": [
            {"role": role, "component_id": f"simulated-{role}"}
            for role in simulated_roles
        ],
        "evidence_refs": list(evidence_refs),
    }
    validate_schema(attestation, "hil-runtime-attestation")
    return attestation


def evaluate_hil_readiness(attestation: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether a declared execution boundary qualifies for v0.5 HIL use.

    Eligibility is deliberately conservative and declaration-based. It is not a
    remote-attestation, TPM, or hardware-certification mechanism.
    """

    validate_schema(attestation, "hil-runtime-attestation")
    real_roles = {item["role"] for item in attestation["real_components"]}
    simulated_roles = {item["role"] for item in attestation["simulated_components"]}

    deployment_environment = attestation["environment"] == "deployment"
    has_real_loop_component = bool(real_roles & _ALLOWED_REAL_ROLES)
    has_simulated_boundary = bool(simulated_roles & _ALLOWED_SIMULATED_ROLES)
    has_external_evidence_ref = bool(attestation["evidence_refs"])
    self_declared = attestation["attestation_trust"] == "self_declared"

    eligible = all(
        (
            deployment_environment,
            has_real_loop_component,
            has_simulated_boundary,
            has_external_evidence_ref,
            self_declared,
        )
    )

    return {
        "deployment_environment": deployment_environment,
        "has_real_loop_component": has_real_loop_component,
        "has_simulated_boundary": has_simulated_boundary,
        "has_external_evidence_ref": has_external_evidence_ref,
        "attestation_is_self_declared": self_declared,
        "eligible": eligible,
    }


def run_hil_reference_experiment(
    profile: RCLProfile,
    target_embodiment: dict[str, Any],
    source_series: dict[str, Any],
    target_series: dict[str, Any],
    adapter: RCLAdapter,
    attestation: dict[str, Any],
    *,
    behavior_id: str,
    expected_target_path_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Compose the semantic reference experiment with an HIL execution boundary.

    A report can pass only when the semantic A -> B experiment passes *and* the
    runtime attestation satisfies the Phase-2 HIL eligibility contract.
    """

    timestamp = created_at or _now()
    readiness = evaluate_hil_readiness(attestation)
    semantic_report = run_simulation_reference_experiment(
        profile,
        target_embodiment,
        source_series,
        target_series,
        adapter,
        behavior_id=behavior_id,
        expected_target_path_id=expected_target_path_id,
        created_at=timestamp,
    )

    semantic_passed = bool(semantic_report["assertions"]["experiment_passed"])
    hil_eligible = bool(readiness["eligible"])
    experiment_passed = semantic_passed and hil_eligible

    if experiment_passed:
        status = "passed"
    elif not hil_eligible:
        status = "not_eligible"
    else:
        status = "semantic_failure"

    report = {
        "hil_reference_version": HIL_REFERENCE_VERSION,
        "method": HIL_REFERENCE_METHOD,
        "created_at": timestamp,
        "evidence_grade": "HIL" if hil_eligible else "UNCLASSIFIED",
        "status": status,
        "attestation": attestation,
        "readiness": readiness,
        "semantic_reference": semantic_report,
        "assertions": {
            "hil_eligible": hil_eligible,
            "semantic_experiment_passed": semantic_passed,
            "experiment_passed": experiment_passed,
        },
        "disclaimer": (
            "HIL Reference Experiment v0.1 treats the runtime attestation as self-declared deployment evidence. "
            "It does not cryptographically verify hardware identity, certify sensor accuracy, validate a physical plant, or substitute for real-robot safety validation."
        ),
    }
    validate_schema(report, "hil-reference-report")
    return report
