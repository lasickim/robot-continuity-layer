from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapter import BehaviorMigrationResult, RCLAdapter
from .migration import migrate_profile
from .profile import RCLProfile, validate_schema
from .score import calculate_continuity_score


SUITE_ID = "rcl.adapter.mobile_base.v0.3"
SUITE_VERSION = "0.3"
COMPATIBILITY_LEVEL = "RCL Migration Compatible"

SOURCE_EMBODIMENT: dict[str, Any] = {
    "embodiment_id": "rcl-conformance-source-mobile-base",
    "vendor": "rcl",
    "model": "conformance-source",
    "class": "mobile_base",
    "capabilities": [
        "navigation.planar_velocity",
        "perception.person_tracking",
        "perception.forward_range",
        "perception.directional_attention",
    ],
    "limits": {
        "max_linear_speed_mps": 0.8,
        "max_angular_speed_rps": 1.0,
    },
    "sensors": ["person_tracker", "range_sensor", "directional_sensor"],
}

TARGET_EMBODIMENT: dict[str, Any] = {
    "embodiment_id": "rcl-conformance-target-mobile-base",
    "vendor": "rcl",
    "model": "conformance-target",
    "class": "mobile_base",
    "capabilities": [
        "navigation.planar_velocity",
        "perception.person_tracking",
        "perception.forward_range",
    ],
    "limits": {
        "max_linear_speed_mps": 1.2,
        "max_angular_speed_rps": 1.4,
    },
    "sensors": ["person_tracker", "range_sensor"],
}

FOLLOW_BEHAVIOR: dict[str, Any] = {
    "behavior_id": "navigation.follow_person",
    "description": "Conformance fixture for portable person-following behavior.",
    "parameters": {
        "preferred_distance_m": 1.4,
        "speed_style": "gentle",
        "turn_style": "cautious",
        "stop_delay_ms": 350,
    },
    "preservation": {"priority": "preferred", "mode": "semantic"},
    "source": "configured",
    "confidence": 1.0,
    "required_capabilities": [
        "navigation.planar_velocity",
        "perception.person_tracking",
    ],
}

PRE_TURN_BEHAVIOR: dict[str, Any] = {
    "behavior_id": "navigation.pre_turn_observation",
    "description": "Conformance fixture for visible optional behavior degradation.",
    "parameters": {
        "minimum_turn_deg": 70,
        "observation_pause_ms": 250,
    },
    "preservation": {"priority": "optional", "mode": "legacy"},
    "source": "configured",
    "confidence": 1.0,
    "required_capabilities": ["perception.directional_attention"],
}


@dataclass(frozen=True)
class ConformanceCheck:
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
            "robot_id": "RCL-CONFORMANCE-SOURCE",
            "display_name": "RCL Conformance Source",
            "continuity_generation": 1,
            "first_activated_at": "2026-08-14T00:00:00Z",
            "previous_profile_id": None,
            "notes": "Synthetic profile used only by the v0.3 adapter conformance suite",
        },
        "preferences": {
            "preferences": [
                {
                    "preference_id": "navigation.follow_person.preferred_distance_m",
                    "scope": "global",
                    "subject_ref": None,
                    "value": 1.4,
                    "source": "configured",
                    "confidence": 1.0,
                }
            ]
        },
        "behavior": {"behaviors": [FOLLOW_BEHAVIOR, PRE_TURN_BEHAVIOR]},
        "skills": {
            "skills": [
                {
                    "skill_id": "navigation.follow_person",
                    "skill_version": "conformance-1",
                    "experience_count": 1,
                    "success_count": 1,
                    "confidence": 1.0,
                    "adaptation": {"comfortable_distance_m": 1.4},
                    "implementation_ref": None,
                }
            ]
        },
        "embodiment": SOURCE_EMBODIMENT,
    }


def _write_fixture_profile(root: Path) -> RCLProfile:
    payloads = _fixture_payloads()
    for name, payload in payloads.items():
        (root / f"{name}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    profile = RCLProfile(root)
    profile.validate(require_manifest=False)
    return profile


def _group_summary(checks: list[ConformanceCheck]) -> dict[str, bool]:
    groups = ["Profile", "Adapter", "Migration", "Safety", "Reporting"]
    return {
        group: all(item.passed for item in checks if item.group == group)
        for group in groups
    }


def run_adapter_conformance(adapter: RCLAdapter) -> dict[str, Any]:
    """Run the experimental v0.3 mobile-base adapter conformance suite.

    The suite verifies protocol behavior and report semantics. It does not
    certify physical motion fidelity, hardware safety, or subjective identity.
    """

    checks: list[ConformanceCheck] = []

    def add(group: str, check_id: str, passed: bool, message: str) -> None:
        checks.append(ConformanceCheck(group, check_id, bool(passed), message))

    # Profile fixture validation.
    try:
        payloads = _fixture_payloads()
        for name, payload in payloads.items():
            validate_schema(payload, name)
        validate_schema(TARGET_EMBODIMENT, "embodiment")
        add("Profile", "fixture.valid", True, "Conformance fixtures validate against published schemas.")
    except Exception as exc:  # pragma: no cover - indicates a broken bundled suite
        add("Profile", "fixture.valid", False, f"Bundled fixture validation failed: {exc}")

    # Adapter identity and target support.
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
        isinstance(adapter_id, str) and bool(adapter_id.strip()) and isinstance(adapter_version, str) and bool(adapter_version.strip()),
        "Adapter declares non-empty adapter_id and adapter_version.",
    )
    try:
        supports = adapter.supports(TARGET_EMBODIMENT)
        add(
            "Adapter",
            "adapter.supports_fixture",
            isinstance(supports, bool) and supports,
            "Adapter explicitly supports the v0.3 mobile-base conformance target.",
        )
    except Exception as exc:
        add("Adapter", "adapter.supports_fixture", False, f"supports() raised: {exc}")

    # Happy-path semantic preservation.
    follow_result: BehaviorMigrationResult | None = None
    try:
        candidate = adapter.translate_behavior(
            FOLLOW_BEHAVIOR,
            SOURCE_EMBODIMENT,
            TARGET_EMBODIMENT,
        )
        if isinstance(candidate, BehaviorMigrationResult):
            follow_result = candidate
            add("Migration", "result.type", True, "translate_behavior() returned BehaviorMigrationResult.")
        else:
            add("Migration", "result.type", False, "translate_behavior() returned an invalid result type.")
    except Exception as exc:
        add("Migration", "result.type", False, f"Happy-path translation raised: {exc}")

    if follow_result is not None:
        add(
            "Migration",
            "follow_person.preserved",
            follow_result.behavior_id == FOLLOW_BEHAVIOR["behavior_id"]
            and follow_result.status == "preserved"
            and follow_result.similarity > 0.0,
            "Supported person-following behavior is reported as preserved with non-zero similarity.",
        )
        add(
            "Migration",
            "follow_person.capabilities",
            not follow_result.missing_capabilities,
            "Supported behavior does not report missing required capabilities.",
        )
    else:
        add("Migration", "follow_person.preserved", False, "No valid happy-path result was produced.")
        add("Migration", "follow_person.capabilities", False, "No valid happy-path result was produced.")

    # Optional behavior whose declared capability is absent on the target must
    # be visible as degradation, never silently called preserved.
    try:
        degraded = adapter.translate_behavior(
            PRE_TURN_BEHAVIOR,
            SOURCE_EMBODIMENT,
            TARGET_EMBODIMENT,
        )
        valid_type = isinstance(degraded, BehaviorMigrationResult)
        add("Migration", "degradation.result_type", valid_type, "Degradation path returns BehaviorMigrationResult.")
        if valid_type:
            visible = degraded.status in {"approximated", "unsupported", "blocked_for_safety"}
            similarity_ok = (
                0.0 < degraded.similarity < 1.0
                if degraded.status == "approximated"
                else degraded.similarity == 0.0
            )
            missing_visible = "perception.directional_attention" in degraded.missing_capabilities
            add(
                "Migration",
                "degradation.visible",
                visible and similarity_ok and missing_visible,
                "Missing optional capability is explicitly approximated, unsupported, or safety-blocked.",
            )
    except Exception as exc:
        add("Migration", "degradation.result_type", False, f"Degradation translation raised: {exc}")
        add("Migration", "degradation.visible", False, "Degradation could not be evaluated.")

    # Required capability removal must force an honest failure result.
    target_missing_person = {
        **TARGET_EMBODIMENT,
        "capabilities": [
            capability
            for capability in TARGET_EMBODIMENT["capabilities"]
            if capability != "perception.person_tracking"
        ],
    }
    required_failure: BehaviorMigrationResult | None = None
    try:
        candidate = adapter.translate_behavior(
            FOLLOW_BEHAVIOR,
            SOURCE_EMBODIMENT,
            target_missing_person,
        )
        if isinstance(candidate, BehaviorMigrationResult):
            required_failure = candidate
            honest_failure = (
                candidate.status in {"unsupported", "blocked_for_safety"}
                and candidate.similarity == 0.0
                and "perception.person_tracking" in candidate.missing_capabilities
            )
            add(
                "Safety",
                "required_capability.honest_failure",
                honest_failure,
                "Missing required person-tracking capability produces an explicit zero-similarity failure.",
            )
        else:
            add("Safety", "required_capability.honest_failure", False, "Required-failure path returned an invalid result type.")
    except Exception as exc:
        add("Safety", "required_capability.honest_failure", False, f"Required-failure translation raised: {exc}")

    if required_failure is not None:
        required_behavior = {
            **FOLLOW_BEHAVIOR,
            "preservation": {"priority": "required", "mode": "semantic"},
        }
        continuity = calculate_continuity_score(
            [required_behavior],
            [required_failure.to_dict()],
        )
        add(
            "Safety",
            "required_capability.blocks_migration",
            continuity["migration_success"] is False
            and FOLLOW_BEHAVIOR["behavior_id"] in continuity["required_failures"],
            "Required behavior failure forces migration_success=false.",
        )
    else:
        add("Safety", "required_capability.blocks_migration", False, "Required-failure result was unavailable.")

    # Full profile -> adapter -> migration report path.
    try:
        with tempfile.TemporaryDirectory(prefix="rcl-conformance-") as tmp:
            profile = _write_fixture_profile(Path(tmp))
            migration_report = migrate_profile(
                profile,
                TARGET_EMBODIMENT,
                adapter,
                created_at="2026-08-14T00:00:00Z",
            )
            validate_schema(migration_report, "migration-report")
        add("Reporting", "migration_report.valid", True, "Full migration report validates against the published schema.")
        statuses = {item["behavior_id"]: item["status"] for item in migration_report["behavior_results"]}
        add(
            "Reporting",
            "migration_report.degradation_visible",
            statuses.get("navigation.follow_person") == "preserved"
            and statuses.get("navigation.pre_turn_observation") in {"approximated", "unsupported", "blocked_for_safety"},
            "Migration report preserves happy-path behavior and exposes optional degradation.",
        )
    except Exception as exc:
        add("Reporting", "migration_report.valid", False, f"Full migration report failed: {exc}")
        add("Reporting", "migration_report.degradation_visible", False, "Migration report degradation could not be evaluated.")

    groups = _group_summary(checks)
    passed = all(groups.values())
    report = {
        "rcl_version": "0.2",
        "suite_id": SUITE_ID,
        "suite_version": SUITE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "adapter": {
            "adapter_id": str(adapter_id),
            "adapter_version": str(adapter_version),
            "python_class": f"{adapter.__class__.__module__}.{adapter.__class__.__qualname__}",
        },
        "passed": passed,
        "compatibility_level": COMPATIBILITY_LEVEL if passed else None,
        "groups": groups,
        "checks": [item.to_dict() for item in checks],
        "disclaimer": "Experimental protocol conformance only; not physical safety certification or identity proof.",
    }
    validate_schema(report, "conformance-report")
    return report
