import copy
import json
from pathlib import Path

import pytest

from rcl.continuity_profile import (
    continuity_profile_summary,
    signature_for_behavior,
    trait_index,
    validate_behavioral_signature,
    validate_continuity_profile,
)
from rcl.profile import PAYLOADS, RCLValidationError


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile() -> dict:
    return _read(
        _root()
        / "examples"
        / "v0.5-continuity"
        / "robot-a.continuity-profile.json"
    )


def test_continuity_profile_example_is_valid():
    profile = _profile()
    validate_continuity_profile(profile)
    signature = signature_for_behavior(
        profile,
        "FOLLOW_USER",
        context={"environment": "home"},
    )
    traits = trait_index(signature)
    assert traits["following_distance"]["value"] == 0.82
    assert traits["lateral_offset"]["value"] == 0.18
    assert traits["gaze_before_move"]["value"] is True


def test_summary_exposes_behavioral_identity_dimensions():
    summary = continuity_profile_summary(_profile())
    assert summary["signature_count"] == 1
    assert summary["trait_count"] == 7
    assert summary["behavior_ids"] == ["FOLLOW_USER"]
    assert "turn_delay" in summary["dimensions"]
    assert "stop_overshoot" in summary["dimensions"]


def test_duplicate_dimension_in_one_signature_is_rejected():
    signature = copy.deepcopy(_profile()["signatures"][0])
    duplicate = copy.deepcopy(signature["traits"][0])
    duplicate["trait_id"] = "different-id"
    signature["traits"].append(duplicate)
    with pytest.raises(RCLValidationError, match="Duplicate behavioral dimension"):
        validate_behavioral_signature(signature)


def test_ambiguous_behavior_signature_requires_context():
    profile = _profile()
    second = copy.deepcopy(profile["signatures"][0])
    second["signature_id"] = "robot-a-follow-user-outdoor"
    second["context"]["environment"] = "outdoor"
    profile["signatures"].append(second)
    validate_continuity_profile(profile)

    with pytest.raises(RCLValidationError, match="found 2"):
        signature_for_behavior(profile, "FOLLOW_USER")

    selected = signature_for_behavior(
        profile,
        "FOLLOW_USER",
        context={"environment": "outdoor"},
    )
    assert selected["signature_id"] == "robot-a-follow-user-outdoor"


def test_continuity_profile_does_not_change_rcl_package_v02_payload_boundary():
    assert "continuity-profile.json" not in PAYLOADS
    assert "behavioral-signature.json" not in PAYLOADS
    assert PAYLOADS == (
        "identity.json",
        "preferences.json",
        "behavior.json",
        "skills.json",
        "embodiment.json",
    )


def test_continuity_schemas_are_published_with_runtime_parity():
    root = _root()
    for name in (
        "behavioral-signature.schema.json",
        "continuity-profile.schema.json",
    ):
        runtime = _read(root / "rcl" / "schemas" / name)
        published = _read(root / "spec" / "schemas" / name)
        assert runtime == published
