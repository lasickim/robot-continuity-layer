import json
from pathlib import Path

import pytest

from rcl.identity_constraint import (
    constraint_for_trait,
    identity_constraint_summary,
    validate_constraints_against_profile,
    validate_identity_constraints,
)
from rcl.profile import RCLValidationError


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile() -> dict:
    return {
        "continuity_profile_version": "0.1",
        "profile_id": "demo",
        "robot_id": "RCL-V05-SIM-A",
        "created_at": "2026-08-17T12:00:00Z",
        "source_embodiment_id": "v05-sim-rover-a",
        "signatures": [
            {
                "behavioral_signature_version": "0.1",
                "signature_id": "follow-home",
                "behavior_id": "FOLLOW_USER",
                "context": {"environment": "home"},
                "traits": [
                    {"trait_id":"distance","dimension":"following_distance","value":0.82,"unit":"m","confidence":0.95,"observed_samples":120},
                    {"trait_id":"gaze","dimension":"gaze_before_move","value":True,"confidence":0.93,"observed_samples":110}
                ]
            }
        ]
    }


def _constraints() -> dict:
    return {
        "identity_constraint_version": "0.1",
        "constraint_set_id": "demo-policy",
        "robot_id": "RCL-V05-SIM-A",
        "constraints": [
            {
                "constraint_id": "distance-policy",
                "behavior_id": "FOLLOW_USER",
                "dimension": "following_distance",
                "context": {"environment": "home"},
                "importance": 0.3,
                "preservation_mode": "preference",
                "substitution_allowed": True,
                "adaptation_allowed": True,
                "tolerance": {"mode": "absolute", "value": 0.08}
            },
            {
                "constraint_id": "gaze-policy",
                "behavior_id": "FOLLOW_USER",
                "dimension": "gaze_before_move",
                "context": {"environment": "home"},
                "importance": 0.95,
                "preservation_mode": "identity_critical",
                "substitution_allowed": True,
                "adaptation_allowed": False,
                "tolerance": {"mode": "exact"}
            }
        ]
    }


def test_constraints_validate_against_observed_profile():
    data = _constraints()
    validate_constraints_against_profile(data, _profile())
    gaze = constraint_for_trait(data, "FOLLOW_USER", "gaze_before_move", context={"environment": "home"})
    assert gaze["importance"] == 0.95
    assert gaze["adaptation_allowed"] is False


def test_constraint_summary_counts_identity_critical_traits():
    summary = identity_constraint_summary(_constraints())
    assert summary["constraint_count"] == 2
    assert summary["identity_critical_count"] == 1
    assert summary["mean_importance"] == pytest.approx(0.625)


def test_constraint_cannot_reference_missing_observed_trait():
    data = _constraints()
    data["constraints"][0]["dimension"] = "nonexistent"
    with pytest.raises(RCLValidationError, match="missing trait"):
        validate_constraints_against_profile(data, _profile())


def test_tolerance_rules_fail_closed():
    data = _constraints()
    data["constraints"][1]["tolerance"] = {"mode": "exact", "value": 0}
    with pytest.raises(RCLValidationError, match="exact tolerance"):
        validate_identity_constraints(data)


def test_relative_tolerance_is_normalized_fraction():
    data = _constraints()
    data["constraints"][0]["tolerance"] = {"mode": "relative", "value": 1.2}
    with pytest.raises(RCLValidationError, match="relative tolerance"):
        validate_identity_constraints(data)


def test_schema_is_published_with_runtime_parity():
    root = _root()
    runtime = _read(root / "rcl" / "schemas" / "identity-constraint.schema.json")
    published = _read(root / "spec" / "schemas" / "identity-constraint.schema.json")
    assert runtime == published
