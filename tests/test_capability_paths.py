import json
import shutil
from pathlib import Path

import pytest

from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.capability_paths import (
    LEGACY_CAPABILITY_PATH_ID,
    evaluate_intent_capability_paths,
    normalized_intent_capability_paths,
    select_satisfied_capability_path,
    validate_intent_capability_paths,
)
from rcl.migration import migrate_profile
from rcl.profile import PAYLOADS, RCLProfile, RCLValidationError


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _base_intent() -> dict:
    return {
        "goal_id": "safety.verify_sitting_area_clear",
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
                "all_of": ["perception.directional_attention"],
                "any_of": [
                    "x.demo.rear_clearance_classifier",
                    "x.demo.rear_occupancy_estimator",
                ],
            },
            {
                "path_id": "external_seat_state",
                "one_of": [
                    "x.demo.external_seat_clearance",
                    "x.demo.networked_seat_clearance",
                ],
            },
        ],
    }


def _profile_with_paths(tmp_path: Path) -> RCLProfile:
    source = _root() / "examples" / "intent" / "sit-assistant-v1"
    target = tmp_path / "profile"
    target.mkdir()
    for name in PAYLOADS:
        shutil.copyfile(source / name, target / name)

    behavior_path = target / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    pre_sit = next(
        item for item in payload["behaviors"]
        if item["behavior_id"] == "safety.pre_sit_clearance_check"
    )
    pre_sit["intent"].pop("required_capabilities")
    pre_sit["intent"]["capability_paths"] = _base_intent()["capability_paths"]
    behavior_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return RCLProfile.open(target)


def _target(embodiment_id: str, capabilities: list[str]) -> dict:
    return {
        "embodiment_id": embodiment_id,
        "vendor": "RCL Demo",
        "model": embodiment_id,
        "class": "other",
        "capabilities": capabilities,
        "sensors": [],
        "limits": {},
        "adapter": {
            "adapter_id": "rcl.reference.capability_paths",
            "adapter_version": "0.4-dev",
        },
    }


def _pre_sit_intent_result(report: dict) -> dict:
    item = next(
        result for result in report["behavior_results"]
        if result["behavior_id"] == "safety.pre_sit_clearance_check"
    )
    return item["intent_result"]


def test_legacy_required_capabilities_normalize_to_all_of_path():
    intent = _base_intent()
    intent.pop("capability_paths")
    intent["required_capabilities"] = ["perception.sitting_area_clearance"]
    paths = normalized_intent_capability_paths(intent)
    assert paths == [
        {
            "path_id": LEGACY_CAPABILITY_PATH_ID,
            "all_of": ["perception.sitting_area_clearance"],
        }
    ]


def test_all_of_and_any_of_clauses_must_both_succeed():
    intent = _base_intent()
    results = evaluate_intent_capability_paths(
        intent,
        {
            "perception.directional_attention",
            "x.demo.rear_occupancy_estimator",
        },
    )
    rear = next(item for item in results if item["path_id"] == "rear_attention_classifier")
    assert rear["satisfied"] is True
    assert rear["selected_capabilities"] == [
        "perception.directional_attention",
        "x.demo.rear_occupancy_estimator",
    ]


def test_any_of_failure_reports_all_options_as_missing():
    intent = _base_intent()
    results = evaluate_intent_capability_paths(
        intent,
        {"perception.directional_attention"},
    )
    rear = next(item for item in results if item["path_id"] == "rear_attention_classifier")
    any_clause = next(item for item in rear["clauses"] if item["clause"] == "any_of")
    assert rear["satisfied"] is False
    assert any_clause["missing"] == [
        "x.demo.rear_clearance_classifier",
        "x.demo.rear_occupancy_estimator",
    ]


def test_one_of_selects_one_deterministically_even_when_multiple_are_available():
    intent = _base_intent()
    result = select_satisfied_capability_path(
        intent,
        {
            "x.demo.external_seat_clearance",
            "x.demo.networked_seat_clearance",
        },
        preferred_path_ids=["external_seat_state"],
    )
    assert result is not None
    assert result["path_id"] == "external_seat_state"
    assert result["selected_capabilities"] == ["x.demo.external_seat_clearance"]
    one_clause = result["clauses"][0]
    assert one_clause["matched"] == [
        "x.demo.external_seat_clearance",
        "x.demo.networked_seat_clearance",
    ]
    assert one_clause["selected"] == ["x.demo.external_seat_clearance"]


def test_duplicate_capability_across_clauses_is_rejected():
    intent = _base_intent()
    intent["capability_paths"][1]["any_of"].append("perception.directional_attention")
    with pytest.raises(RCLValidationError, match="same capability"):
        validate_intent_capability_paths(intent)


def test_intent_must_use_exactly_one_legacy_or_path_representation():
    intent = _base_intent()
    intent["required_capabilities"] = ["perception.sitting_area_clearance"]
    with pytest.raises(RCLValidationError, match="exactly one"):
        validate_intent_capability_paths(intent)


def test_direct_target_preserves_same_goal_via_direct_path(tmp_path):
    profile = _profile_with_paths(tmp_path)
    report = migrate_profile(
        profile,
        _target(
            "cap-path-direct",
            [
                "perception.sitting_area_clearance",
                "manipulation.handover_orientation",
            ],
        ),
        CapabilityPathReferenceAdapter(),
        created_at="2026-08-15T02:30:00Z",
    )
    result = _pre_sit_intent_result(report)
    assert result["status"] == "preserved"
    assert result["selected_capability_path_id"] == "direct_clearance"
    assert result["target_strategy"] == "target.direct_clearance_state"
    assert report["continuity"]["migration_success"] is True


def test_rear_attention_target_preserves_same_goal_via_combined_path(tmp_path):
    profile = _profile_with_paths(tmp_path)
    report = migrate_profile(
        profile,
        _target(
            "cap-path-rear",
            [
                "perception.directional_attention",
                "x.demo.rear_clearance_classifier",
                "manipulation.handover_orientation",
            ],
        ),
        CapabilityPathReferenceAdapter(),
        created_at="2026-08-15T02:31:00Z",
    )
    result = _pre_sit_intent_result(report)
    assert result["status"] == "preserved"
    assert result["selected_capability_path_id"] == "rear_attention_classifier"
    assert result["target_strategy"] == "target.rear_attention_clearance"


def test_external_state_target_preserves_same_goal_via_one_of_path(tmp_path):
    profile = _profile_with_paths(tmp_path)
    report = migrate_profile(
        profile,
        _target(
            "cap-path-external",
            [
                "x.demo.external_seat_clearance",
                "manipulation.handover_orientation",
            ],
        ),
        CapabilityPathReferenceAdapter(),
        created_at="2026-08-15T02:32:00Z",
    )
    result = _pre_sit_intent_result(report)
    assert result["status"] == "preserved"
    assert result["selected_capability_path_id"] == "external_seat_state"
    assert result["target_strategy"] == "target.external_seat_clearance"


def test_no_satisfied_path_hard_fails_required_intent_with_per_path_diagnostics(tmp_path):
    profile = _profile_with_paths(tmp_path)
    report = migrate_profile(
        profile,
        _target(
            "cap-path-none",
            ["manipulation.handover_orientation"],
        ),
        CapabilityPathReferenceAdapter(),
        created_at="2026-08-15T02:33:00Z",
    )
    result = _pre_sit_intent_result(report)
    assert result["status"] == "unsupported"
    assert result["selected_capability_path_id"] is None
    assert len(result["capability_path_results"]) == 3
    assert all(not item["satisfied"] for item in result["capability_path_results"])
    assert "intent:safety.pre_sit_clearance_check" in report["continuity"]["required_failures"]
    assert report["continuity"]["migration_success"] is False
