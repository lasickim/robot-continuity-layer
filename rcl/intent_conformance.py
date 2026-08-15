from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapter import ExpressionMigrationResult, IntentMigrationResult, RCLAdapter
from .capability_paths import (
    LEGACY_CAPABILITY_PATH_ID,
    evaluate_intent_capability_paths,
    normalized_intent_capability_paths,
)
from .migration import migrate_profile
from .profile import RCLProfile, validate_schema


INTENT_CONFORMANCE_SUITE_ID = "rcl.adapter.intent.v0.4"
INTENT_CONFORMANCE_SUITE_VERSION = "0.1"
INTENT_CONFORMANCE_COMPATIBILITY_LEVEL = "RCL Intent Migration Compatible"

GOAL_ID = "safety.verify_sitting_area_clear"
BEHAVIOR_ID = "safety.pre_sit_clearance_check"

SOURCE_EMBODIMENT: dict[str, Any] = {
    "embodiment_id": "rcl-intent-conformance-source",
    "vendor": "rcl",
    "model": "intent-conformance-source",
    "class": "other",
    "capabilities": [
        "perception.sitting_area_clearance",
        "perception.directional_attention",
        "x.rcl-conformance.rear_clearance_classifier",
        "x.rcl-conformance.external_seat_clearance",
    ],
    "sensors": ["source_semantic_fixture"],
    "limits": {},
}

DIRECT_TARGET: dict[str, Any] = {
    "embodiment_id": "rcl-intent-conformance-direct",
    "vendor": "rcl",
    "model": "intent-conformance-direct",
    "class": "other",
    "capabilities": [
        "perception.sitting_area_clearance",
        "perception.directional_attention",
    ],
    "sensors": ["direct_clearance_fixture"],
    "limits": {},
}

ALTERNATE_TARGET: dict[str, Any] = {
    "embodiment_id": "rcl-intent-conformance-alternate",
    "vendor": "rcl",
    "model": "intent-conformance-alternate",
    "class": "other",
    "capabilities": [
        "perception.directional_attention",
        "x.rcl-conformance.rear_clearance_classifier",
    ],
    "sensors": ["alternate_clearance_fixture"],
    "limits": {},
}

NO_PATH_TARGET: dict[str, Any] = {
    "embodiment_id": "rcl-intent-conformance-no-path",
    "vendor": "rcl",
    "model": "intent-conformance-no-path",
    "class": "other",
    "capabilities": ["perception.directional_attention"],
    "sensors": ["expression_only_fixture"],
    "limits": {},
}

PATH_INTENT: dict[str, Any] = {
    "goal_id": GOAL_ID,
    "description": "Verify the intended sitting area before sitting.",
    "trigger": "activity.before_sit_down",
    "success_condition": "state.sitting_area_clear",
    "failure_action": "block",
    "criticality": "required",
    "capability_paths": [
        {
            "path_id": "direct_clearance",
            "all_of": ["perception.sitting_area_clearance"],
        },
        {
            "path_id": "rear_attention_classifier",
            "all_of": [
                "perception.directional_attention",
                "x.rcl-conformance.rear_clearance_classifier",
            ],
        },
        {
            "path_id": "external_seat_state",
            "all_of": ["x.rcl-conformance.external_seat_clearance"],
        },
    ],
    "constraints": ["safety.no_unverified_sit"],
}

PATH_BEHAVIOR: dict[str, Any] = {
    "behavior_id": BEHAVIOR_ID,
    "description": "Intent-aware conformance behavior with alternative capability paths.",
    "parameters": {},
    "required_capabilities": [],
    "intent": PATH_INTENT,
    "expression": {
        "expression_id": "observation.brief_rearward_check",
        "description": "Visible legacy glance used to verify expression/Intent separation.",
        "preservation_priority": "optional",
        "required_capabilities": ["perception.directional_attention"],
    },
    "preservation": {"priority": "required", "mode": "semantic"},
    "source": "configured",
    "confidence": 1.0,
}

LEGACY_BEHAVIOR: dict[str, Any] = {
    **PATH_BEHAVIOR,
    "behavior_id": "safety.pre_sit_clearance_check_legacy",
    "intent": {
        **{key: value for key, value in PATH_INTENT.items() if key != "capability_paths"},
        "required_capabilities": ["perception.sitting_area_clearance"],
    },
    "expression": None,
}
LEGACY_BEHAVIOR.pop("expression")


@dataclass(frozen=True)
class IntentConformanceCheck:
    group: str
    check_id: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "check_id": self.check_id,
            "passed": self.passed,
            "message": self.message,
        }


def _fixture_payloads() -> dict[str, dict[str, Any]]:
    return {
        "identity": {
            "robot_id": "RCL-INTENT-CONFORMANCE-SOURCE",
            "display_name": "RCL Intent Conformance Source",
            "continuity_generation": 1,
            "first_activated_at": "2026-08-15T00:00:00Z",
            "previous_profile_id": None,
            "notes": "Synthetic profile used only by the v0.4 Intent adapter conformance suite",
        },
        "preferences": {"preferences": []},
        "behavior": {"behaviors": [PATH_BEHAVIOR]},
        "skills": {"skills": []},
        "embodiment": SOURCE_EMBODIMENT,
    }


def _write_fixture_profile(root: Path) -> RCLProfile:
    for name, payload in _fixture_payloads().items():
        (root / f"{name}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    profile = RCLProfile(root)
    profile.validate(require_manifest=False)
    return profile


def _group_summary(checks: list[IntentConformanceCheck]) -> dict[str, bool]:
    groups = ["Profile", "Adapter", "Intent", "Paths", "Safety", "Reporting"]
    return {
        group: all(item.passed for item in checks if item.group == group)
        for group in groups
    }


def _path_result_map(result: IntentMigrationResult) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("path_id")): item
        for item in result.capability_path_results
        if isinstance(item, dict) and item.get("path_id") is not None
    }


def _expected_satisfied_paths(target: dict[str, Any]) -> set[str]:
    results = evaluate_intent_capability_paths(
        PATH_INTENT,
        target.get("capabilities", []),
    )
    return {item["path_id"] for item in results if item["satisfied"]}


def _check_preserved_result(
    result: Any,
    target: dict[str, Any],
    *,
    expected_path_id: str,
) -> tuple[bool, bool, bool, bool]:
    if not isinstance(result, IntentMigrationResult):
        return False, False, False, False

    satisfied = _expected_satisfied_paths(target)
    declared_ids = {item["path_id"] for item in normalized_intent_capability_paths(PATH_INTENT)}
    path_map = _path_result_map(result)

    intent_ok = (
        result.goal_id == GOAL_ID
        and result.status == "preserved"
        and isinstance(result.target_strategy, str)
        and bool(result.target_strategy.strip())
    )
    selected_ok = (
        result.selected_capability_path_id == expected_path_id
        and expected_path_id in satisfied
        and expected_path_id in declared_ids
    )
    diagnostics_ok = set(path_map) == declared_ids and all(
        isinstance(path_map[path_id].get("satisfied"), bool) for path_id in declared_ids
    )
    selected_diagnostic_ok = (
        expected_path_id in path_map
        and path_map[expected_path_id].get("satisfied") is True
    )
    return intent_ok, selected_ok, diagnostics_ok, selected_diagnostic_ok


def run_intent_adapter_conformance(adapter: RCLAdapter) -> dict[str, Any]:
    """Run the experimental v0.4 Intent-aware adapter conformance suite.

    The suite checks report honesty for declared Intent and capability paths. It
    does not certify physical sensing correctness, observed goal success, or
    hardware safety.
    """

    checks: list[IntentConformanceCheck] = []

    def add(group: str, check_id: str, passed: bool, message: str) -> None:
        checks.append(IntentConformanceCheck(group, check_id, bool(passed), message))

    try:
        payloads = _fixture_payloads()
        for name, payload in payloads.items():
            validate_schema(payload, name)
        for target in (DIRECT_TARGET, ALTERNATE_TARGET, NO_PATH_TARGET):
            validate_schema(target, "embodiment")
        add("Profile", "fixture.valid", True, "Intent conformance fixtures validate against published schemas.")
    except Exception as exc:  # pragma: no cover
        add("Profile", "fixture.valid", False, f"Bundled fixture validation failed: {exc}")

    add(
        "Adapter",
        "adapter.type",
        isinstance(adapter, RCLAdapter),
        "Adapter subclasses RCLAdapter." if isinstance(adapter, RCLAdapter) else "Adapter does not subclass RCLAdapter.",
    )
    adapter_id = getattr(adapter, "adapter_id", "")
    adapter_version = getattr(adapter, "adapter_version", "")
    add(
        "Adapter",
        "adapter.metadata",
        isinstance(adapter_id, str)
        and bool(adapter_id.strip())
        and isinstance(adapter_version, str)
        and bool(adapter_version.strip()),
        "Adapter declares non-empty adapter_id and adapter_version.",
    )
    try:
        support_values = [adapter.supports(target) for target in (DIRECT_TARGET, ALTERNATE_TARGET, NO_PATH_TARGET)]
        add(
            "Adapter",
            "adapter.supports_fixtures",
            all(isinstance(value, bool) and value for value in support_values),
            "Adapter explicitly supports all Intent conformance target embodiments.",
        )
    except Exception as exc:
        add("Adapter", "adapter.supports_fixtures", False, f"supports() raised: {exc}")

    direct_result: IntentMigrationResult | None = None
    try:
        candidate = adapter.translate_intent(PATH_BEHAVIOR, SOURCE_EMBODIMENT, DIRECT_TARGET)
        direct_result = candidate if isinstance(candidate, IntentMigrationResult) else None
        intent_ok, selected_ok, diagnostics_ok, selected_diag_ok = _check_preserved_result(
            candidate,
            DIRECT_TARGET,
            expected_path_id="direct_clearance",
        )
        add("Intent", "direct.intent_preserved", intent_ok, "Direct target preserves the exact declared Intent with a target-native strategy.")
        add("Paths", "direct.selected_path_truthful", selected_ok, "Direct target selects the actually satisfied direct_clearance path.")
        add("Paths", "direct.path_diagnostics_complete", diagnostics_ok and selected_diag_ok, "Direct result reports every declared path and marks the selected path satisfied.")
    except Exception as exc:
        add("Intent", "direct.intent_preserved", False, f"Direct Intent translation raised: {exc}")
        add("Paths", "direct.selected_path_truthful", False, "Direct path could not be evaluated.")
        add("Paths", "direct.path_diagnostics_complete", False, "Direct path diagnostics could not be evaluated.")

    alternate_result: IntentMigrationResult | None = None
    try:
        candidate = adapter.translate_intent(PATH_BEHAVIOR, SOURCE_EMBODIMENT, ALTERNATE_TARGET)
        alternate_result = candidate if isinstance(candidate, IntentMigrationResult) else None
        intent_ok, selected_ok, diagnostics_ok, selected_diag_ok = _check_preserved_result(
            candidate,
            ALTERNATE_TARGET,
            expected_path_id="rear_attention_classifier",
        )
        add("Intent", "alternate.intent_preserved", intent_ok, "Alternate target preserves the same Intent through a different semantic capability path.")
        add("Paths", "alternate.not_flattened", selected_ok, "Alternative paths remain OR alternatives rather than being flattened into one all-required set.")
        add("Paths", "alternate.path_diagnostics_complete", diagnostics_ok and selected_diag_ok, "Alternate result reports complete truthful path diagnostics.")
    except Exception as exc:
        add("Intent", "alternate.intent_preserved", False, f"Alternate Intent translation raised: {exc}")
        add("Paths", "alternate.not_flattened", False, "Alternate path could not be evaluated.")
        add("Paths", "alternate.path_diagnostics_complete", False, "Alternate path diagnostics could not be evaluated.")

    no_path_result: IntentMigrationResult | None = None
    expression_result: ExpressionMigrationResult | None = None
    try:
        candidate = adapter.translate_intent(PATH_BEHAVIOR, SOURCE_EMBODIMENT, NO_PATH_TARGET)
        no_path_result = candidate if isinstance(candidate, IntentMigrationResult) else None
        honest_failure = (
            isinstance(candidate, IntentMigrationResult)
            and candidate.goal_id == GOAL_ID
            and candidate.status in {"unsupported", "blocked_for_safety"}
            and candidate.selected_capability_path_id is None
            and not _expected_satisfied_paths(NO_PATH_TARGET)
        )
        add("Intent", "no_path.honest_failure", honest_failure, "A target satisfying no functional path is never reported as Intent-preserved.")

        expr = adapter.translate_expression(PATH_BEHAVIOR, SOURCE_EMBODIMENT, NO_PATH_TARGET)
        expression_result = expr if isinstance(expr, ExpressionMigrationResult) else None
        expression_available = (
            isinstance(expr, ExpressionMigrationResult)
            and expr.status == "preserved"
        )
        add("Safety", "expression.not_intent_substitute", honest_failure and expression_available, "A reproducible legacy expression does not substitute for an unsatisfied functional Intent.")
    except Exception as exc:
        add("Intent", "no_path.honest_failure", False, f"No-path Intent translation raised: {exc}")
        add("Safety", "expression.not_intent_substitute", False, "Expression/Intent separation could not be evaluated.")

    try:
        legacy = adapter.translate_intent(LEGACY_BEHAVIOR, SOURCE_EMBODIMENT, DIRECT_TARGET)
        legacy_map = _path_result_map(legacy) if isinstance(legacy, IntentMigrationResult) else {}
        legacy_ok = (
            isinstance(legacy, IntentMigrationResult)
            and legacy.status == "preserved"
            and legacy.selected_capability_path_id == LEGACY_CAPABILITY_PATH_ID
            and LEGACY_CAPABILITY_PATH_ID in legacy_map
            and legacy_map[LEGACY_CAPABILITY_PATH_ID].get("satisfied") is True
        )
        add("Paths", "legacy.required_capabilities_compatible", legacy_ok, "Legacy flat required_capabilities remain one implicit all_of capability path.")
    except Exception as exc:
        add("Paths", "legacy.required_capabilities_compatible", False, f"Legacy Intent compatibility raised: {exc}")

    direct_report: dict[str, Any] | None = None
    no_path_report: dict[str, Any] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="rcl-intent-conformance-") as tmp:
            profile = _write_fixture_profile(Path(tmp))
            direct_report = migrate_profile(
                profile,
                DIRECT_TARGET,
                adapter,
                created_at="2026-08-15T00:00:00Z",
            )
            no_path_report = migrate_profile(
                profile,
                NO_PATH_TARGET,
                adapter,
                created_at="2026-08-15T00:00:00Z",
            )
            validate_schema(direct_report, "migration-report")
            validate_schema(no_path_report, "migration-report")
        add("Reporting", "migration_reports.valid", True, "Direct and no-path full migration reports validate against the published migration schema.")
    except Exception as exc:
        add("Reporting", "migration_reports.valid", False, f"Full migration reporting failed: {exc}")

    if direct_report is not None:
        item = next((entry for entry in direct_report["behavior_results"] if entry["behavior_id"] == BEHAVIOR_ID), None)
        intent = (item or {}).get("intent_result") or {}
        add(
            "Reporting",
            "migration_report.selected_path",
            intent.get("status") == "preserved"
            and intent.get("selected_capability_path_id") == "direct_clearance",
            "Full migration report exposes the truthful selected capability path.",
        )
    else:
        add("Reporting", "migration_report.selected_path", False, "Direct migration report was unavailable.")

    if no_path_report is not None:
        continuity = no_path_report["continuity"]
        item = next((entry for entry in no_path_report["behavior_results"] if entry["behavior_id"] == BEHAVIOR_ID), None)
        intent = (item or {}).get("intent_result") or {}
        hard_failure = (
            continuity["migration_success"] is False
            and f"intent:{BEHAVIOR_ID}" in continuity.get("intent_required_failures", [])
            and intent.get("status") in {"unsupported", "blocked_for_safety"}
        )
        add("Safety", "required_intent.blocks_migration", hard_failure, "Unsatisfied required Intent forces migration_success=false, including safety-blocked results.")
    else:
        add("Safety", "required_intent.blocks_migration", False, "No-path migration report was unavailable.")

    groups = _group_summary(checks)
    passed = all(groups.values())
    report = {
        "rcl_version": "0.2",
        "suite_id": INTENT_CONFORMANCE_SUITE_ID,
        "suite_version": INTENT_CONFORMANCE_SUITE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "adapter": {
            "adapter_id": str(adapter_id),
            "adapter_version": str(adapter_version),
            "python_class": f"{adapter.__class__.__module__}.{adapter.__class__.__qualname__}",
        },
        "passed": passed,
        "compatibility_level": INTENT_CONFORMANCE_COMPATIBILITY_LEVEL if passed else None,
        "groups": groups,
        "checks": [item.to_dict() for item in checks],
        "disclaimer": (
            "Experimental Intent/report protocol conformance only; not physical safety certification, "
            "sensor validation, observed goal-success proof, consciousness, or identity proof."
        ),
    }
    validate_schema(report, "intent-conformance-report")
    return report
