import copy
import json
from pathlib import Path

from rcl.compatibility_mapping import map_behavioral_compatibility


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "v0.5-continuity"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs():
    return (
        _read(EXAMPLES / "robot-a.continuity-profile.json"),
        _read(EXAMPLES / "identity-constraints.example.json"),
        _read(EXAMPLES / "robot-b.capability-manifest.json"),
    )


def _mapping(report: dict, dimension: str) -> dict:
    return next(item for item in report["mappings"] if item["dimension"] == dimension)


def test_reference_robot_a_to_b_mapping():
    profile, constraints, manifest = _inputs()
    report = map_behavioral_compatibility(
        profile,
        constraints,
        manifest,
        created_at="2026-08-20T10:00:00Z",
    )

    assert report["summary"]["counts"] == {
        "EXACT": 6,
        "APPROXIMATE": 0,
        "SUBSTITUTE": 1,
        "UNSUPPORTED": 0,
    }
    assert report["summary"]["all_constraints_satisfied"] is True
    gaze = _mapping(report, "gaze_before_move")
    assert gaze["classification"] == "SUBSTITUTE"
    assert gaze["substitution_strategy"] == "body_yaw_attention_cue"
    assert gaze["constraint_satisfied"] is True


def test_numeric_resolution_can_be_approximate_but_policy_satisfied():
    profile, constraints, manifest = _inputs()
    profile = copy.deepcopy(profile)
    for trait in profile["signatures"][0]["traits"]:
        if trait["dimension"] == "turn_delay":
            trait["value"] = 175

    report = map_behavioral_compatibility(profile, constraints, manifest)
    delay = _mapping(report, "turn_delay")
    assert delay["classification"] == "APPROXIMATE"
    assert delay["target_value"] == 180
    assert delay["absolute_error"] == 5
    assert delay["constraint_satisfied"] is True


def test_approximate_mapping_can_violate_identity_tolerance():
    profile, constraints, manifest = _inputs()
    profile = copy.deepcopy(profile)
    constraints = copy.deepcopy(constraints)
    for trait in profile["signatures"][0]["traits"]:
        if trait["dimension"] == "turn_delay":
            trait["value"] = 175
    for item in constraints["constraints"]:
        if item["dimension"] == "turn_delay":
            item["tolerance"] = {"mode": "absolute", "value": 2}

    report = map_behavioral_compatibility(profile, constraints, manifest)
    delay = _mapping(report, "turn_delay")
    assert delay["classification"] == "APPROXIMATE"
    assert delay["constraint_satisfied"] is False
    assert report["summary"]["all_constraints_satisfied"] is False


def test_forbidden_substitution_is_unsupported():
    profile, constraints, manifest = _inputs()
    constraints = copy.deepcopy(constraints)
    for item in constraints["constraints"]:
        if item["dimension"] == "gaze_before_move":
            item["substitution_allowed"] = False

    report = map_behavioral_compatibility(profile, constraints, manifest)
    gaze = _mapping(report, "gaze_before_move")
    assert gaze["classification"] == "UNSUPPORTED"
    assert gaze["reason"] == "substitution_forbidden"
    assert gaze["constraint_satisfied"] is False


def test_missing_target_support_is_unsupported():
    profile, constraints, manifest = _inputs()
    manifest = copy.deepcopy(manifest)
    manifest["capabilities"] = [
        cap
        for cap in manifest["capabilities"]
        if cap["capability_id"] != "expression.body_orientation_attention"
    ]

    report = map_behavioral_compatibility(profile, constraints, manifest)
    gaze = _mapping(report, "gaze_before_move")
    assert gaze["classification"] == "UNSUPPORTED"
    assert gaze["reason"] == "no_target_support"


def test_unit_mismatch_is_unsupported():
    profile, constraints, manifest = _inputs()
    manifest = copy.deepcopy(manifest)
    for cap in manifest["capabilities"]:
        for support in cap["supports"]:
            if support["dimension"] == "following_distance":
                support["unit"] = "cm"

    report = map_behavioral_compatibility(profile, constraints, manifest)
    distance = _mapping(report, "following_distance")
    assert distance["classification"] == "UNSUPPORTED"
    assert distance["reason"] == "unit_mismatch"


def test_schema_is_published_with_runtime_parity():
    runtime = _read(ROOT / "rcl" / "schemas" / "compatibility-mapping-report.schema.json")
    published = _read(ROOT / "spec" / "schemas" / "compatibility-mapping-report.schema.json")
    assert runtime == published
