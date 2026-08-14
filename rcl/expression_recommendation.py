from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any

from .expression_history import expression_sha256
from .profile import RCLProfile, RCLValidationError, validate_schema


EXPRESSION_RECOMMENDATION_VERSION = "0.1"
EXPRESSION_RECOMMENDATION_METHOD = "rcl.expression.optimization.recommendation.v0.1"
DEFAULT_EXPRESSION_RECOMMENDATION_POLICY_RESOURCE = (
    "expression-optimization-recommendation-policy-v0.1.json"
)

_DECISIONS = {
    "review_removal",
    "review_simplification",
    "retain",
    "inconclusive",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _profile_id(profile: RCLProfile) -> str | None:
    manifest = profile.root / "manifest.json"
    if not manifest.exists():
        return None
    return profile.load("manifest.json")["profile_id"]


def load_default_expression_optimization_policy() -> dict[str, Any]:
    resource = files("rcl").joinpath(
        "data", DEFAULT_EXPRESSION_RECOMMENDATION_POLICY_RESOURCE
    )
    policy = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(policy, "expression-optimization-recommendation-policy")
    return policy


def _gate(name: str, *, actual: Any, required: Any, passed: bool) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "actual": actual,
        "required": required,
    }


def _behavior_map(profile: RCLProfile) -> dict[str, dict[str, Any]]:
    return {
        item["behavior_id"]: item
        for item in profile.load("behavior.json")["behaviors"]
    }


def _result_map(items: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        behavior_id = item["behavior_id"]
        if behavior_id in result:
            raise RCLValidationError(f"Duplicate {label} result for behavior: {behavior_id}")
        result[behavior_id] = item
    return result


def _validate_report_relationships(
    profile: RCLProfile,
    migration_report: dict[str, Any],
    intent_success_report: dict[str, Any],
) -> None:
    validate_schema(migration_report, "migration-report")
    validate_schema(intent_success_report, "observed-intent-success-report")

    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")
    robot_id = identity["robot_id"]
    embodiment_id = embodiment["embodiment_id"]

    if migration_report["source"]["robot_id"] != robot_id:
        raise RCLValidationError("Migration report source robot does not match the profile")
    if migration_report["source"]["embodiment_id"] != embodiment_id:
        raise RCLValidationError("Migration report source embodiment does not match the profile")

    profile_id = _profile_id(profile)
    migration_profile_id = migration_report["source"].get("profile_id")
    if profile_id is not None and migration_profile_id is not None and migration_profile_id != profile_id:
        raise RCLValidationError("Migration report source profile_id does not match the profile")

    declared = intent_success_report["declared_profile"]
    if declared["robot_id"] != robot_id or declared["embodiment_id"] != embodiment_id:
        raise RCLValidationError("Observed Intent Success declared profile does not match the profile")

    target_embodiment = migration_report["target"]["embodiment_id"]
    observed_embodiment = intent_success_report["observed_subject"]["embodiment_id"]
    if target_embodiment != observed_embodiment:
        raise RCLValidationError(
            "Migration target embodiment does not match Observed Intent Success subject"
        )


def _legacy_significance(expression: dict[str, Any]) -> str:
    temporal_style = expression.get("temporal_style")
    if not isinstance(temporal_style, dict):
        return "unspecified"
    return temporal_style.get("legacy_significance", "unspecified")


def _decision_details(decision: str) -> tuple[str | None, str, str]:
    if decision == "review_removal":
        return (
            "remove",
            "review_remove_candidate",
            "Functional evidence supports reviewing whether this optional incidental expression should remain active.",
        )
    if decision == "review_simplification":
        return (
            "simplify",
            "design_replacement_then_review",
            "Functional evidence supports reviewing a simpler expression, but RCL does not invent the replacement gesture.",
        )
    if decision == "retain":
        return (
            None,
            "retain_expression",
            "Current evidence or continuity significance favors retaining the expression.",
        )
    return (
        None,
        "collect_more_evidence",
        "The available evidence is insufficient or not directly comparable for an optimization recommendation.",
    )


def _recommendation_id(
    *,
    behavior_id: str,
    expression_sha: str,
    target_embodiment_id: str,
    migration_sha: str,
    intent_success_sha: str,
    policy_sha: str,
) -> str:
    material = {
        "behavior_id": behavior_id,
        "expression_sha256": expression_sha,
        "target_embodiment_id": target_embodiment_id,
        "migration_report_sha256": migration_sha,
        "intent_success_report_sha256": intent_success_sha,
        "policy_sha256": policy_sha,
    }
    return f"expr-rec-{_sha256_json(material)[:16]}"


def evaluate_expression_optimization_recommendations(
    profile: RCLProfile,
    migration_report: dict[str, Any],
    intent_success_report: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Recommend review of legacy expressions without mutating continuity data.

    v0.1 combines declared migration evidence with Observed Intent Success. It can
    recommend review, but it never proves causal redundancy and never creates or
    applies an expression optimization candidate.
    """

    selected_policy = policy or load_default_expression_optimization_policy()
    validate_schema(selected_policy, "expression-optimization-recommendation-policy")
    _validate_report_relationships(profile, migration_report, intent_success_report)

    behavior_map = _behavior_map(profile)
    migration_map = _result_map(migration_report["behavior_results"], label="migration")
    success_map = _result_map(intent_success_report["intent_results"], label="Intent Success")

    migration_sha = _sha256_json(migration_report)
    success_sha = _sha256_json(intent_success_report)
    policy_sha = _sha256_json(selected_policy)
    target_embodiment = migration_report["target"]["embodiment_id"]

    recommendations: list[dict[str, Any]] = []

    for behavior_id in sorted(behavior_map):
        behavior = behavior_map[behavior_id]
        expression = behavior.get("expression")
        if expression is None:
            continue

        migration_item = migration_map.get(behavior_id)
        if migration_item is None:
            raise RCLValidationError(
                f"Migration report is missing active-expression behavior: {behavior_id}"
            )

        expression_result = migration_item.get("expression_result")
        if expression_result is None:
            raise RCLValidationError(
                f"Migration report is missing expression_result for {behavior_id}"
            )
        if expression_result["expression_id"] != expression["expression_id"]:
            raise RCLValidationError(
                f"{behavior_id}: migration expression_id does not match current profile expression"
            )

        timing_result = migration_item.get("expression_timing_result")
        if timing_result is not None and timing_result["expression_id"] != expression["expression_id"]:
            raise RCLValidationError(
                f"{behavior_id}: migration expression timing result does not match current expression"
            )

        intent = behavior.get("intent")
        significance = _legacy_significance(expression)
        priority = expression["preservation_priority"]
        gates: list[dict[str, Any]] = []
        intent_evidence = {
            "goal_id": None,
            "success_condition": None,
            "migration_status": None,
            "target_strategy": None,
            "observed_status": None,
            "observed_strategy_id": None,
        }
        expression_evidence = {
            "migration_status": expression_result["status"],
            "timing_status": None if timing_result is None else timing_result["status"],
        }
        evidence_refs: list[str] = []

        if intent is None:
            gates.append(
                _gate(
                    "declared_intent",
                    actual=False,
                    required=True,
                    passed=False,
                )
            )
            decision = selected_policy["missing_evidence_decision"]
        else:
            migration_intent = migration_item.get("intent_result")
            if migration_intent is None:
                raise RCLValidationError(
                    f"Migration report is missing intent_result for {behavior_id}"
                )
            success_item = success_map.get(behavior_id)
            if success_item is None:
                raise RCLValidationError(
                    f"Observed Intent Success report is missing behavior: {behavior_id}"
                )

            if migration_intent["goal_id"] != intent["goal_id"]:
                raise RCLValidationError(
                    f"{behavior_id}: migration goal_id does not match current Intent"
                )
            if success_item["goal_id"] != intent["goal_id"]:
                raise RCLValidationError(
                    f"{behavior_id}: observed goal_id does not match current Intent"
                )
            if success_item["trigger"] != intent["trigger"]:
                raise RCLValidationError(
                    f"{behavior_id}: observed trigger does not match current Intent"
                )
            if success_item["success_condition"] != intent["success_condition"]:
                raise RCLValidationError(
                    f"{behavior_id}: observed success condition does not match current Intent"
                )

            target_strategy = migration_intent["target_strategy"]
            observed_strategy = success_item["strategy_id"]
            evidence_refs = list(success_item.get("evidence_refs", []))
            intent_evidence = {
                "goal_id": intent["goal_id"],
                "success_condition": intent["success_condition"],
                "migration_status": migration_intent["status"],
                "target_strategy": target_strategy,
                "observed_status": success_item["status"],
                "observed_strategy_id": observed_strategy,
            }

            migration_ok = (
                migration_intent["status"]
                == selected_policy["require_intent_migration_status"]
            )
            observed_ok = (
                success_item["status"]
                == selected_policy["require_observed_intent_status"]
            )
            target_strategy_present = target_strategy is not None
            if selected_policy["require_strategy_match"]:
                strategy_ok = (
                    target_strategy is not None
                    and observed_strategy is not None
                    and target_strategy == observed_strategy
                )
            else:
                strategy_ok = target_strategy_present

            statuses = [
                migration_item["status"],
                migration_intent["status"],
                expression_result["status"],
            ]
            if timing_result is not None:
                statuses.append(timing_result["status"])
            safety_ok = "blocked_for_safety" not in statuses
            expression_available = expression_result["status"] in {
                "preserved",
                "approximated",
            }
            if timing_result is not None:
                expression_available = expression_available and timing_result["status"] in {
                    "naturalized",
                    "preserved",
                    "approximated",
                }

            gates.extend(
                [
                    _gate(
                        "declared_intent",
                        actual=True,
                        required=True,
                        passed=True,
                    ),
                    _gate(
                        "intent_migration_status",
                        actual=migration_intent["status"],
                        required=selected_policy["require_intent_migration_status"],
                        passed=migration_ok,
                    ),
                    _gate(
                        "observed_intent_status",
                        actual=success_item["status"],
                        required=selected_policy["require_observed_intent_status"],
                        passed=observed_ok,
                    ),
                    _gate(
                        "target_strategy_declared",
                        actual=target_strategy,
                        required="non-null",
                        passed=target_strategy_present,
                    ),
                    _gate(
                        "observed_strategy_matches_target_strategy",
                        actual={
                            "migration": target_strategy,
                            "observed": observed_strategy,
                        },
                        required=("equal" if selected_policy["require_strategy_match"] else "target strategy declared"),
                        passed=strategy_ok,
                    ),
                    _gate(
                        "no_expression_or_intent_safety_block",
                        actual=statuses,
                        required="no blocked_for_safety",
                        passed=safety_ok,
                    ),
                    _gate(
                        "expression_representable_on_target",
                        actual={
                            "expression": expression_result["status"],
                            "timing": None if timing_result is None else timing_result["status"],
                        },
                        required="preserved/approximated target expression",
                        passed=expression_available,
                    ),
                ]
            )

            if not safety_ok:
                decision = selected_policy["safety_block_decision"]
            elif not migration_ok or not observed_ok or not expression_available:
                decision = "retain"
            elif not target_strategy_present or not strategy_ok:
                decision = selected_policy["missing_evidence_decision"]
            else:
                decision = selected_policy["decision_matrix"][priority][significance]

        if decision not in _DECISIONS:
            raise RCLValidationError(f"Unsupported expression recommendation decision: {decision}")

        suggested_action, next_action, reason = _decision_details(decision)
        expression_sha = expression_sha256(expression)
        recommendations.append(
            {
                "recommendation_id": _recommendation_id(
                    behavior_id=behavior_id,
                    expression_sha=expression_sha,
                    target_embodiment_id=target_embodiment,
                    migration_sha=migration_sha,
                    intent_success_sha=success_sha,
                    policy_sha=policy_sha,
                ),
                "behavior_id": behavior_id,
                "expression_id": expression["expression_id"],
                "preservation_priority": priority,
                "legacy_significance": significance,
                "decision": decision,
                "suggested_action": suggested_action,
                "recommended_next_action": next_action,
                "reason": reason,
                "gates": gates,
                "intent_evidence": intent_evidence,
                "expression_evidence": expression_evidence,
                "evidence_refs": evidence_refs,
                "redundancy_proven": False,
            }
        )

    counts = {decision: 0 for decision in _DECISIONS}
    for item in recommendations:
        counts[item["decision"]] += 1

    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")
    report = {
        "recommendation_version": EXPRESSION_RECOMMENDATION_VERSION,
        "method": EXPRESSION_RECOMMENDATION_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": {
            "policy_id": selected_policy["policy_id"],
            "policy_version": selected_policy["policy_version"],
            "policy_sha256": policy_sha,
        },
        "source_profile": {
            "robot_id": identity["robot_id"],
            "embodiment_id": embodiment["embodiment_id"],
        },
        "target": {
            "embodiment_id": target_embodiment,
            "observed_robot_id": intent_success_report["observed_subject"]["robot_id"],
        },
        "migration_report_sha256": migration_sha,
        "intent_success_report_sha256": success_sha,
        "recommendations": recommendations,
        "summary": {
            "total": len(recommendations),
            "review_removal": counts["review_removal"],
            "review_simplification": counts["review_simplification"],
            "retain": counts["retain"],
            "inconclusive": counts["inconclusive"],
        },
        "non_mutating": True,
        "redundancy_proven": False,
        "disclaimer": (
            "Expression Optimization Recommendation v0.1 recommends review only. "
            "It does not prove causal redundancy, infer user preference, certify safety, "
            "invent a replacement expression, mutate the profile, or bypass explicit optimization approval."
        ),
    }
    validate_schema(report, "expression-optimization-recommendation-report")
    return report
