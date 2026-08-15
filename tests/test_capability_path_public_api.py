from rcl import (
    CAPABILITY_PATHS_VERSION,
    LEGACY_CAPABILITY_PATH_ID,
    CapabilityPathReferenceAdapter,
    IntentMigrationResult,
    evaluate_intent_capability_paths,
    select_satisfied_capability_path,
)


def test_capability_path_public_api_is_exported():
    assert CAPABILITY_PATHS_VERSION == "0.1"
    assert LEGACY_CAPABILITY_PATH_ID == "legacy.required_capabilities"
    assert CapabilityPathReferenceAdapter.adapter_id == "rcl.reference.capability_paths"
    assert callable(evaluate_intent_capability_paths)
    assert callable(select_satisfied_capability_path)


def test_legacy_intent_migration_result_backfills_path_diagnostics():
    result = IntentMigrationResult(
        goal_id="safety.verify_sitting_area_clear",
        status="preserved",
        reason="legacy adapter result",
        target_strategy="target.legacy_strategy",
        required_capabilities=("perception.sitting_area_clearance",),
    ).to_dict()

    assert result["selected_capability_path_id"] == LEGACY_CAPABILITY_PATH_ID
    assert len(result["capability_path_results"]) == 1
    path = result["capability_path_results"][0]
    assert path["path_id"] == LEGACY_CAPABILITY_PATH_ID
    assert path["satisfied"] is True
    assert path["clauses"][0]["clause"] == "all_of"
