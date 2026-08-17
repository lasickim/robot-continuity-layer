import json
from pathlib import Path

import pytest

from rcl.capability_manifest import (
    capability_manifest_summary,
    preferred_support_for_dimension,
    supports_for_dimension,
    validate_capability_manifest,
)
from rcl.profile import RCLValidationError


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return _read(_root() / "examples" / "v0.5-continuity" / "robot-b.capability-manifest.json")


def test_reference_manifest_validates_and_exposes_direct_support():
    manifest = _manifest()
    validate_capability_manifest(manifest)
    support = preferred_support_for_dimension(manifest, "following_distance")
    assert support is not None
    assert support["capability_id"] == "locomotion.following_geometry"
    assert support["support"]["mapping_mode"] == "direct"
    assert support["support"]["resolution"] == 0.01


def test_reference_manifest_exposes_substitute_for_gaze():
    manifest = _manifest()
    support = preferred_support_for_dimension(manifest, "gaze_before_move")
    assert support is not None
    assert support["support"]["mapping_mode"] == "substitute"
    assert support["support"]["substitution_strategy"] == "body_yaw_attention_cue"
    assert supports_for_dimension(manifest, "gaze_before_move", mapping_mode="direct") == []


def test_unknown_dimension_has_no_support():
    assert preferred_support_for_dimension(_manifest(), "custom_handshake") is None


def test_substitute_requires_strategy():
    manifest = _manifest()
    support = manifest["capabilities"][-1]["supports"][0]
    del support["substitution_strategy"]
    with pytest.raises(RCLValidationError, match="substitution_strategy"):
        validate_capability_manifest(manifest)


def test_numeric_range_must_be_ordered():
    manifest = _manifest()
    support = manifest["capabilities"][0]["supports"][0]
    support["minimum"] = 4.0
    support["maximum"] = 1.0
    with pytest.raises(RCLValidationError, match="minimum"):
        validate_capability_manifest(manifest)


def test_categorical_support_requires_allowed_values():
    manifest = _manifest()
    support = manifest["capabilities"][1]["supports"][0]
    del support["allowed_values"]
    with pytest.raises(RCLValidationError, match="allowed_values"):
        validate_capability_manifest(manifest)


def test_summary_separates_direct_and_substitute_dimensions():
    summary = capability_manifest_summary(_manifest())
    assert summary["capability_count"] == 4
    assert "following_distance" in summary["direct_dimensions"]
    assert "gaze_before_move" in summary["substitute_dimensions"]
    assert "gaze_before_move" not in summary["direct_dimensions"]


def test_schema_is_published_with_runtime_parity():
    root = _root()
    runtime = _read(root / "rcl" / "schemas" / "capability-manifest.schema.json")
    published = _read(root / "spec" / "schemas" / "capability-manifest.schema.json")
    assert runtime == published
