from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .adapter import RCLAdapter
from .migration import migrate_profile
from .profile import RCLProfile, RCLValidationError, validate_schema
from .repeated_intent_success import evaluate_repeated_intent_success


SIMULATION_REFERENCE_VERSION = "0.1"
SIMULATION_REFERENCE_METHOD = "rcl.simulation.reference_migration.v0.5"


def _intent_summary(report: dict[str, Any], behavior_id: str) -> dict[str, Any]:
    for item in report["intent_summaries"]:
        if item["behavior_id"] == behavior_id:
            return item
    raise RCLValidationError(
        f"Repeated Intent Success report has no summary for behavior {behavior_id!r}"
    )


def _behavior_migration(report: dict[str, Any], behavior_id: str) -> dict[str, Any]:
    for item in report["behavior_results"]:
        if item["behavior_id"] == behavior_id:
            return item
    raise RCLValidationError(
        f"Migration report has no result for behavior {behavior_id!r}"
    )


def run_simulation_reference_experiment(
    profile: RCLProfile,
    target_embodiment: dict[str, Any],
    source_series: dict[str, Any],
    target_series: dict[str, Any],
    adapter: RCLAdapter,
    *,
    behavior_id: str,
    expected_target_path_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Run a deterministic Robot A -> Robot B semantic continuity experiment.

    This v0.5 reference harness deliberately does not simulate rigid-body physics.
    It composes the existing migration and repeated Intent Success evaluators so a
    source embodiment and a different target embodiment can demonstrate the same
    declared WHY through different observed execution strategies.
    """

    timestamp = created_at or datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )

    migration = migrate_profile(
        profile,
        target_embodiment,
        adapter,
        created_at=timestamp,
    )
    source_success = evaluate_repeated_intent_success(
        profile,
        source_series,
        created_at=timestamp,
    )
    target_success = evaluate_repeated_intent_success(
        profile,
        target_series,
        created_at=timestamp,
    )

    behavior_migration = _behavior_migration(migration, behavior_id)
    intent_migration = behavior_migration.get("intent_result")
    if intent_migration is None:
        raise RCLValidationError(
            f"Behavior {behavior_id!r} has no Intent migration result"
        )

    source_summary = _intent_summary(source_success, behavior_id)
    target_summary = _intent_summary(target_success, behavior_id)

    source_strategy_ids = list(source_summary["observed_strategy_ids"])
    target_strategy_ids = list(target_summary["observed_strategy_ids"])
    selected_path_id = intent_migration.get("selected_capability_path_id")
    target_strategy = intent_migration.get("target_strategy")
    expression_result = behavior_migration.get("expression_result")

    source_goal_estimated = (
        source_success["evaluation_success"] is True
        and source_summary["status"] == "estimated"
    )
    target_goal_estimated = (
        target_success["evaluation_success"] is True
        and target_summary["status"] == "estimated"
    )
    migration_success = bool(migration["continuity"]["migration_success"])
    intent_preserved = intent_migration["status"] == "preserved"
    target_path_selected = selected_path_id is not None
    target_selected_expected_path = (
        target_path_selected
        if expected_target_path_id is None
        else selected_path_id == expected_target_path_id
    )
    strategies_differ = (
        bool(source_strategy_ids)
        and bool(target_strategy_ids)
        and set(source_strategy_ids) != set(target_strategy_ids)
    )
    target_strategy_observed = (
        target_strategy is not None and target_strategy in target_strategy_ids
    )

    experiment_passed = all(
        (
            source_goal_estimated,
            target_goal_estimated,
            migration_success,
            intent_preserved,
            target_selected_expected_path,
            strategies_differ,
            target_strategy_observed,
        )
    )

    report = {
        "simulation_reference_version": SIMULATION_REFERENCE_VERSION,
        "method": SIMULATION_REFERENCE_METHOD,
        "created_at": timestamp,
        "behavior_id": behavior_id,
        "goal_id": source_summary["goal_id"],
        "source": {
            "robot_id": source_series["robot_id"],
            "embodiment_id": source_series["embodiment_id"],
            "observed_strategy_ids": source_strategy_ids,
            "repeated_intent_status": source_summary["status"],
            "observed_success_rate": source_summary["observed_success_rate"],
        },
        "target": {
            "robot_id": target_series["robot_id"],
            "embodiment_id": target_series["embodiment_id"],
            "observed_strategy_ids": target_strategy_ids,
            "repeated_intent_status": target_summary["status"],
            "observed_success_rate": target_summary["observed_success_rate"],
        },
        "migration": {
            "migration_success": migration_success,
            "behavior_status": behavior_migration["status"],
            "intent_status": intent_migration["status"],
            "selected_capability_path_id": selected_path_id,
            "target_strategy": target_strategy,
            "expression_status": (
                None if expression_result is None else expression_result["status"]
            ),
        },
        "assertions": {
            "source_goal_estimated": source_goal_estimated,
            "target_goal_estimated": target_goal_estimated,
            "migration_success": migration_success,
            "intent_preserved": intent_preserved,
            "target_selected_expected_path": target_selected_expected_path,
            "strategies_differ": strategies_differ,
            "target_strategy_observed": target_strategy_observed,
            "experiment_passed": experiment_passed,
        },
        "disclaimer": (
            "Simulation Reference Experiment v0.1 validates semantic migration and repeated declared Intent success using deterministic synthetic observations. "
            "It does not simulate rigid-body physics, certify physical safety, or substitute for hardware-in-the-loop or real-robot validation."
        ),
    }
    validate_schema(report, "simulation-reference-report")
    return report
