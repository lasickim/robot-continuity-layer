from __future__ import annotations

from datetime import datetime, timezone
from math import isclose
from typing import Any

from .continuity_profile import signature_for_behavior, trait_index, validate_continuity_profile
from .identity_constraint import validate_constraints_against_profile
from .profile import RCLValidationError, validate_schema


CONTINUITY_SCORE_VERSION = "0.1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _constraint_index(constraints: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["constraint_id"]: item for item in constraints["constraints"]}


def _trait_for_constraint(
    profile: dict[str, Any], constraint: dict[str, Any]
) -> dict[str, Any]:
    signature = signature_for_behavior(
        profile,
        constraint["behavior_id"],
        context=constraint.get("context"),
    )
    return trait_index(signature)[constraint["dimension"]]


def _approximate_fidelity(
    mapping: dict[str, Any], constraint: dict[str, Any]
) -> float:
    if "absolute_error" not in mapping:
        return 0.0
    error = float(mapping["absolute_error"])
    tolerance = constraint["tolerance"]
    mode = tolerance["mode"]
    if mode == "exact":
        return 1.0 if isclose(error, 0.0, abs_tol=1e-9) else 0.0
    if mode == "absolute":
        allowed = float(tolerance["value"])
        if allowed <= 0:
            return 1.0 if isclose(error, 0.0, abs_tol=1e-9) else 0.0
        return max(0.0, min(1.0, 1.0 - error / allowed))
    if mode == "relative":
        source = mapping.get("source_value")
        if not isinstance(source, (int, float)) or isinstance(source, bool):
            return 0.0
        allowed = float(tolerance["value"])
        if allowed <= 0:
            return 1.0 if isclose(error, 0.0, abs_tol=1e-9) else 0.0
        source_abs = abs(float(source))
        if isclose(source_abs, 0.0, abs_tol=1e-12):
            return 1.0 if isclose(error, 0.0, abs_tol=1e-9) else 0.0
        relative_error = error / source_abs
        return max(0.0, min(1.0, 1.0 - relative_error / allowed))
    raise RCLValidationError(f"Unsupported tolerance mode: {mode}")


def _validate_substitution_assessments(
    assessments: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if assessments is None:
        return {}
    for constraint_id, item in assessments.items():
        fidelity = item.get("fidelity")
        if not isinstance(fidelity, (int, float)) or isinstance(fidelity, bool):
            raise RCLValidationError(
                f"Substitution assessment {constraint_id} requires numeric fidelity"
            )
        if not 0.0 <= float(fidelity) <= 1.0:
            raise RCLValidationError(
                f"Substitution assessment {constraint_id} fidelity must be in 0..1"
            )
        evidence_refs = item.get("evidence_refs", [])
        if not isinstance(evidence_refs, list) or any(
            not isinstance(ref, str) or not ref for ref in evidence_refs
        ):
            raise RCLValidationError(
                f"Substitution assessment {constraint_id} evidence_refs must be strings"
            )
    return assessments


def score_behavioral_continuity(
    profile: dict[str, Any],
    constraints: dict[str, Any],
    compatibility_report: dict[str, Any],
    *,
    substitution_assessments: dict[str, dict[str, Any]] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score behavioral continuity without inventing substitute quality.

    Direct mappings receive deterministic fidelity. Approved substitutes remain
    unresolved unless an external evidence-backed fidelity assessment is
    supplied. Therefore v0.1 reports lower/upper score bounds and only emits a
    resolved_score when every weighted trait has a resolved fidelity.
    """

    validate_continuity_profile(profile)
    validate_constraints_against_profile(constraints, profile)
    validate_schema(compatibility_report, "compatibility-mapping-report")
    assessments = _validate_substitution_assessments(substitution_assessments)

    if compatibility_report["source_robot_id"] != profile["robot_id"]:
        raise RCLValidationError("compatibility report source_robot_id mismatch")
    if compatibility_report["source_profile_id"] != profile["profile_id"]:
        raise RCLValidationError("compatibility report source_profile_id mismatch")
    if compatibility_report["constraint_set_id"] != constraints["constraint_set_id"]:
        raise RCLValidationError("compatibility report constraint_set_id mismatch")

    constraints_by_id = _constraint_index(constraints)
    seen_mapping_ids: set[str] = set()
    trait_scores: list[dict[str, Any]] = []
    total_weight = 0.0
    lower_sum = 0.0
    upper_sum = 0.0
    policy_sum = 0.0
    resolved_weight = 0.0
    identity_critical_failures: list[str] = []

    for mapping in compatibility_report["mappings"]:
        constraint_id = mapping["constraint_id"]
        if constraint_id in seen_mapping_ids:
            raise RCLValidationError(f"Duplicate compatibility mapping: {constraint_id}")
        seen_mapping_ids.add(constraint_id)
        if constraint_id not in constraints_by_id:
            raise RCLValidationError(
                f"Compatibility mapping references unknown constraint: {constraint_id}"
            )

        constraint = constraints_by_id[constraint_id]
        trait = _trait_for_constraint(profile, constraint)
        confidence = float(trait.get("confidence", 1.0))
        importance = float(constraint["importance"])
        effective_weight = importance * confidence
        total_weight += effective_weight

        classification = mapping["classification"]
        fidelity: float | None
        lower: float
        upper: float
        assessment_refs: list[str] = []

        if classification == "EXACT":
            fidelity = 1.0
            lower = upper = 1.0
        elif classification == "APPROXIMATE":
            fidelity = _approximate_fidelity(mapping, constraint)
            lower = upper = fidelity
        elif classification == "UNSUPPORTED":
            fidelity = 0.0
            lower = upper = 0.0
        elif classification == "SUBSTITUTE":
            assessment = assessments.get(constraint_id)
            if assessment is None:
                fidelity = None
                lower, upper = 0.0, 1.0
            else:
                fidelity = float(assessment["fidelity"])
                lower = upper = fidelity
                assessment_refs = list(assessment.get("evidence_refs", []))
        else:
            raise RCLValidationError(f"Unsupported mapping classification: {classification}")

        lower_sum += effective_weight * lower
        upper_sum += effective_weight * upper
        if fidelity is not None:
            resolved_weight += effective_weight
        if mapping["constraint_satisfied"]:
            policy_sum += effective_weight
        elif constraint["preservation_mode"] == "identity_critical":
            identity_critical_failures.append(constraint_id)

        item: dict[str, Any] = {
            "constraint_id": constraint_id,
            "behavior_id": mapping["behavior_id"],
            "dimension": mapping["dimension"],
            "classification": classification,
            "importance": importance,
            "source_confidence": confidence,
            "effective_weight": effective_weight,
            "preservation_mode": constraint["preservation_mode"],
            "constraint_satisfied": mapping["constraint_satisfied"],
            "fidelity_lower": lower,
            "fidelity_upper": upper,
        }
        if fidelity is not None:
            item["fidelity"] = fidelity
        if assessment_refs:
            item["assessment_evidence_refs"] = assessment_refs
        trait_scores.append(item)

    missing = set(constraints_by_id) - seen_mapping_ids
    if missing:
        raise RCLValidationError(
            "Compatibility report is missing constraints: " + ", ".join(sorted(missing))
        )
    if total_weight <= 0:
        raise RCLValidationError("Continuity score requires positive effective weight")

    lower_score = lower_sum / total_weight
    upper_score = upper_sum / total_weight
    resolved = isclose(lower_score, upper_score, abs_tol=1e-12)
    score_summary: dict[str, Any] = {
        "lower_bound": lower_score,
        "upper_bound": upper_score,
        "policy_coverage_score": policy_sum / total_weight,
        "resolved_weight_fraction": resolved_weight / total_weight,
        "identity_critical_ok": not identity_critical_failures,
        "identity_critical_failures": sorted(identity_critical_failures),
    }
    if resolved:
        score_summary["resolved_score"] = lower_score

    report = {
        "continuity_score_version": CONTINUITY_SCORE_VERSION,
        "created_at": created_at or _now(),
        "source_robot_id": compatibility_report["source_robot_id"],
        "source_profile_id": compatibility_report["source_profile_id"],
        "constraint_set_id": compatibility_report["constraint_set_id"],
        "target_robot_id": compatibility_report["target_robot_id"],
        "target_embodiment_id": compatibility_report["target_embodiment_id"],
        "trait_scores": trait_scores,
        "summary": score_summary,
    }
    validate_schema(report, "continuity-score-report")
    return report
