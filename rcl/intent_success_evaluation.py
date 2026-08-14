from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .profile import RCLProfile, RCLValidationError, validate_schema


INTENT_SUCCESS_EVALUATION_VERSION = "0.1"
INTENT_SUCCESS_EVALUATION_METHOD = "rcl.observed.intent_success.v0.1"


def _declared_intents(profile: RCLProfile) -> dict[str, dict[str, Any]]:
    payload = profile.load("behavior.json")
    return {
        behavior["behavior_id"]: behavior
        for behavior in payload["behaviors"]
        if behavior.get("intent") is not None
    }


def _validate_observations(
    declared: dict[str, dict[str, Any]], observations: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    validate_schema(observations, "intent-observations")

    seen_ids: set[str] = set()
    by_behavior: dict[str, dict[str, Any]] = {}
    for observation in observations["intent_observations"]:
        observation_id = observation["observation_id"]
        behavior_id = observation["behavior_id"]

        if observation_id in seen_ids:
            raise RCLValidationError(f"Duplicate intent observation_id: {observation_id}")
        seen_ids.add(observation_id)

        if behavior_id in by_behavior:
            raise RCLValidationError(f"Duplicate intent observation for behavior: {behavior_id}")
        if behavior_id not in declared:
            raise RCLValidationError(
                f"Intent observation references unknown or intent-less behavior: {behavior_id}"
            )

        intent = declared[behavior_id]["intent"]
        if observation["trigger"] != intent["trigger"]:
            raise RCLValidationError(
                f"{behavior_id}: observed trigger {observation['trigger']!r} does not match declared trigger {intent['trigger']!r}"
            )
        if observation["success_condition"] != intent["success_condition"]:
            raise RCLValidationError(
                f"{behavior_id}: observed success_condition {observation['success_condition']!r} does not match declared success_condition {intent['success_condition']!r}"
            )
        if observation["trigger_state"] == "not_observed" and observation["success_state"] != "not_observable":
            raise RCLValidationError(
                f"{behavior_id}: success_state must be not_observable when the declared trigger was not observed"
            )

        by_behavior[behavior_id] = observation
    return by_behavior


def _evaluate_one(
    behavior: dict[str, Any], observation: dict[str, Any] | None
) -> dict[str, Any]:
    behavior_id = behavior["behavior_id"]
    intent = behavior["intent"]
    criticality = intent["criticality"]

    if observation is None:
        status = "not_observable"
        reason = "missing_observation"
        observation_id = None
        trigger_state = None
        success_state = None
        strategy_id = None
        evidence_refs: list[str] = []
        observation_present = False
    else:
        observation_present = True
        observation_id = observation["observation_id"]
        trigger_state = observation["trigger_state"]
        success_state = observation["success_state"]
        strategy_id = observation.get("strategy_id")
        evidence_refs = list(observation.get("evidence_refs", []))

        if trigger_state == "not_observed":
            status = "not_triggered"
            reason = "declared_trigger_not_observed"
        elif success_state == "satisfied":
            status = "pass"
            reason = "declared_success_condition_satisfied"
        elif success_state == "not_satisfied":
            status = "fail"
            reason = "declared_success_condition_not_satisfied"
        else:
            status = "not_observable"
            reason = "declared_success_condition_not_observable"

    blocking = criticality == "required" and status != "pass"
    return {
        "behavior_id": behavior_id,
        "goal_id": intent["goal_id"],
        "criticality": criticality,
        "trigger": intent["trigger"],
        "success_condition": intent["success_condition"],
        "observation_present": observation_present,
        "observation_id": observation_id,
        "trigger_state": trigger_state,
        "success_state": success_state,
        "strategy_id": strategy_id,
        "evidence_refs": evidence_refs,
        "status": status,
        "blocking": blocking,
        "reason": reason,
    }


def evaluate_observed_intent_success(
    profile: RCLProfile,
    observations: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate declared engineering intent success independently from motion similarity.

    v0.1 evaluates one controlled observation per behavior. Target-native strategy is
    retained as audit metadata only and never affects pass/fail logic.
    """

    declared = _declared_intents(profile)
    if not declared:
        raise RCLValidationError("Profile declares no behavior intents to evaluate")

    observed_by_behavior = _validate_observations(declared, observations)
    results = [
        _evaluate_one(declared[behavior_id], observed_by_behavior.get(behavior_id))
        for behavior_id in sorted(declared)
    ]

    required_failures = [
        item["behavior_id"]
        for item in results
        if item["criticality"] == "required" and item["status"] == "fail"
    ]
    required_inconclusive = [
        item["behavior_id"]
        for item in results
        if item["criticality"] == "required"
        and item["status"] in {"not_observable", "not_triggered"}
    ]
    nonblocking_failures = [
        item["behavior_id"]
        for item in results
        if item["criticality"] != "required" and item["status"] != "pass"
    ]

    if required_failures:
        status = "failed"
        evaluation_success: bool | None = False
    elif required_inconclusive:
        status = "inconclusive"
        evaluation_success = None
    else:
        status = "passed"
        evaluation_success = True

    identity = profile.load("identity.json")
    embodiment = profile.load("embodiment.json")
    report = {
        "evaluation_version": INTENT_SUCCESS_EVALUATION_VERSION,
        "method": INTENT_SUCCESS_EVALUATION_METHOD,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "declared_profile": {
            "robot_id": identity["robot_id"],
            "embodiment_id": embodiment["embodiment_id"],
        },
        "observed_subject": {
            "robot_id": observations["robot_id"],
            "embodiment_id": observations["embodiment_id"],
            "captured_at": observations["captured_at"],
        },
        "status": status,
        "evaluation_success": evaluation_success,
        "required_failures": required_failures,
        "required_inconclusive": required_inconclusive,
        "nonblocking_failures": nonblocking_failures,
        "intent_results": results,
        "disclaimer": (
            "Observed Intent Success v0.1 evaluates whether declared engineering success conditions were observed. "
            "It does not measure motion similarity, subjective motivation, consciousness, causal truth, or certified physical safety."
        ),
    }
    validate_schema(report, "observed-intent-success-report")
    return report
