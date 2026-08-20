from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .profile import RCLValidationError, validate_schema


BEHAVIOR_COMPILER_VERSION = "0.1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compile_behavior_preserving_plan(
    compatibility_report: dict[str, Any],
    continuity_score_report: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Compile compatibility decisions into an adapter-facing target plan.

    READY: direct mappings that satisfy identity policy.
    REVIEW_REQUIRED: approved substitutions whose behavioral fidelity is unresolved.
    BLOCKED: unsupported mappings or mappings that violate identity policy.
    """

    validate_schema(compatibility_report, "compatibility-mapping-report")
    validate_schema(continuity_score_report, "continuity-score-report")

    linkage_fields = (
        "source_robot_id",
        "source_profile_id",
        "constraint_set_id",
        "target_robot_id",
        "target_embodiment_id",
    )
    for field in linkage_fields:
        if compatibility_report[field] != continuity_score_report[field]:
            raise RCLValidationError(f"compiler input mismatch: {field}")

    score_by_constraint = {
        item["constraint_id"]: item for item in continuity_score_report["trait_scores"]
    }
    if len(score_by_constraint) != len(continuity_score_report["trait_scores"]):
        raise RCLValidationError("duplicate constraint_id in continuity score report")

    instructions: list[dict[str, Any]] = []
    for mapping in compatibility_report["mappings"]:
        constraint_id = mapping["constraint_id"]
        if constraint_id not in score_by_constraint:
            raise RCLValidationError(
                f"continuity score missing constraint: {constraint_id}"
            )
        score_item = score_by_constraint[constraint_id]
        if score_item["classification"] != mapping["classification"]:
            raise RCLValidationError(
                f"classification mismatch for constraint: {constraint_id}"
            )

        classification = mapping["classification"]
        policy_ok = bool(mapping["constraint_satisfied"])
        instruction: dict[str, Any] = {
            "constraint_id": constraint_id,
            "behavior_id": mapping["behavior_id"],
            "dimension": mapping["dimension"],
            "classification": classification,
            "preservation_mode": mapping["preservation_mode"],
            "constraint_satisfied": policy_ok,
        }

        if classification in ("EXACT", "APPROXIMATE"):
            if not policy_ok:
                instruction.update(
                    {
                        "execution_status": "BLOCKED",
                        "reason": "identity_constraint_not_satisfied",
                    }
                )
            else:
                instruction.update(
                    {
                        "execution_status": "READY",
                        "reason": "direct_target_mapping",
                        "capability_id": mapping["capability_id"],
                        "mapping_mode": "direct",
                        "target_value": mapping["target_value"],
                    }
                )
                if "absolute_error" in mapping:
                    instruction["absolute_error"] = mapping["absolute_error"]

        elif classification == "SUBSTITUTE":
            if not policy_ok:
                instruction.update(
                    {
                        "execution_status": "BLOCKED",
                        "reason": "substitution_not_allowed_by_identity_policy",
                    }
                )
            else:
                fidelity_resolved = "fidelity" in score_item
                instruction.update(
                    {
                        "execution_status": "READY" if fidelity_resolved else "REVIEW_REQUIRED",
                        "reason": (
                            "evidence_resolved_substitution"
                            if fidelity_resolved
                            else "substitution_fidelity_unresolved"
                        ),
                        "capability_id": mapping["capability_id"],
                        "mapping_mode": "substitute",
                        "substitution_strategy": mapping["substitution_strategy"],
                    }
                )
                if fidelity_resolved:
                    instruction["assessed_fidelity"] = score_item["fidelity"]
                    if "assessment_evidence_refs" in score_item:
                        instruction["assessment_evidence_refs"] = score_item[
                            "assessment_evidence_refs"
                        ]

        elif classification == "UNSUPPORTED":
            instruction.update(
                {
                    "execution_status": "BLOCKED",
                    "reason": mapping["reason"],
                }
            )
        else:
            raise RCLValidationError(
                f"unsupported compiler classification: {classification}"
            )

        instructions.append(instruction)

    statuses = {name: 0 for name in ("READY", "REVIEW_REQUIRED", "BLOCKED")}
    for item in instructions:
        statuses[item["execution_status"]] += 1

    critical_blocked = [
        item["constraint_id"]
        for item in instructions
        if item["preservation_mode"] == "identity_critical"
        and item["execution_status"] == "BLOCKED"
    ]

    plan_status = "READY"
    if critical_blocked or statuses["BLOCKED"]:
        plan_status = "BLOCKED"
    elif statuses["REVIEW_REQUIRED"]:
        plan_status = "REVIEW_REQUIRED"

    report = {
        "behavior_compiler_version": BEHAVIOR_COMPILER_VERSION,
        "created_at": created_at or _now(),
        "source_robot_id": compatibility_report["source_robot_id"],
        "source_profile_id": compatibility_report["source_profile_id"],
        "constraint_set_id": compatibility_report["constraint_set_id"],
        "target_robot_id": compatibility_report["target_robot_id"],
        "target_embodiment_id": compatibility_report["target_embodiment_id"],
        "instructions": instructions,
        "summary": {
            "plan_status": plan_status,
            "instruction_count": len(instructions),
            "status_counts": statuses,
            "identity_critical_blocked": sorted(critical_blocked),
            "continuity_lower_bound": continuity_score_report["summary"][
                "lower_bound"
            ],
            "continuity_upper_bound": continuity_score_report["summary"][
                "upper_bound"
            ],
        },
    }
    if "resolved_score" in continuity_score_report["summary"]:
        report["summary"]["resolved_continuity_score"] = continuity_score_report[
            "summary"
        ]["resolved_score"]

    validate_schema(report, "behavior-compiler-plan")
    return report
