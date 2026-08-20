from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcl.compatibility_mapping import map_behavioral_compatibility
from rcl.continuity_score import score_behavioral_continuity
from rcl.profile import RCLValidationError


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "v0.5-continuity"


def _read(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict, dict]:
    profile = _read("robot-a.continuity-profile.json")
    constraints = _read("identity-constraints.example.json")
    target = _read("robot-b.capability-manifest.json")
    mapping = map_behavioral_compatibility(
        profile,
        constraints,
        target,
        created_at="2026-08-20T10:00:00Z",
    )
    return profile, constraints, target, mapping


def test_unassessed_substitute_produces_score_bounds():
    profile, constraints, _, mapping = _inputs()
    report = score_behavioral_continuity(
        profile,
        constraints,
        mapping,
        created_at="2026-08-20T11:00:00Z",
    )

    assert report["summary"]["lower_bound"] == pytest.approx(0.7756951813)
    assert report["summary"]["upper_bound"] == pytest.approx(1.0)
    assert report["summary"]["resolved_weight_fraction"] == pytest.approx(
        report["summary"]["lower_bound"]
    )
    assert report["summary"]["policy_coverage_score"] == pytest.approx(1.0)
    assert report["summary"]["identity_critical_ok"] is True
    assert "resolved_score" not in report["summary"]

    gaze = next(
        item for item in report["trait_scores"] if item["dimension"] == "gaze_before_move"
    )
    assert gaze["classification"] == "SUBSTITUTE"
    assert "fidelity" not in gaze
    assert gaze["fidelity_lower"] == 0.0
    assert gaze["fidelity_upper"] == 1.0


def test_evidence_backed_substitute_resolves_score():
    profile, constraints, _, mapping = _inputs()
    report = score_behavioral_continuity(
        profile,
        constraints,
        mapping,
        substitution_assessments={
            "follow-gaze": {
                "fidelity": 0.8,
                "evidence_refs": ["physical://robot-b/gaze-substitute-study/run-01"],
            }
        },
        created_at="2026-08-20T11:00:00Z",
    )

    assert report["summary"]["lower_bound"] == pytest.approx(0.9551401022)
    assert report["summary"]["upper_bound"] == pytest.approx(0.9551401022)
    assert report["summary"]["resolved_score"] == pytest.approx(0.9551401022)
    assert report["summary"]["resolved_weight_fraction"] == pytest.approx(1.0)

    gaze = next(
        item for item in report["trait_scores"] if item["dimension"] == "gaze_before_move"
    )
    assert gaze["fidelity"] == 0.8
    assert gaze["assessment_evidence_refs"] == [
        "physical://robot-b/gaze-substitute-study/run-01"
    ]


def test_approximate_fidelity_uses_identity_tolerance():
    profile, constraints, _, mapping = _inputs()
    delay = next(item for item in mapping["mappings"] if item["dimension"] == "turn_delay")
    delay["classification"] = "APPROXIMATE"
    delay["reason"] = "nearest_reachable_value"
    delay["source_value"] = 170
    delay["target_value"] = 180
    delay["absolute_error"] = 10
    delay["constraint_satisfied"] = True

    report = score_behavioral_continuity(
        profile,
        constraints,
        mapping,
        created_at="2026-08-20T11:00:00Z",
    )
    scored_delay = next(
        item for item in report["trait_scores"] if item["dimension"] == "turn_delay"
    )
    assert scored_delay["fidelity"] == pytest.approx(0.75)


def test_identity_critical_policy_failure_is_flagged():
    profile, constraints, _, mapping = _inputs()
    gaze = next(item for item in mapping["mappings"] if item["dimension"] == "gaze_before_move")
    gaze["classification"] = "UNSUPPORTED"
    gaze["constraint_satisfied"] = False
    gaze["reason"] = "substitution_forbidden"

    report = score_behavioral_continuity(
        profile,
        constraints,
        mapping,
        created_at="2026-08-20T11:00:00Z",
    )
    assert report["summary"]["identity_critical_ok"] is False
    assert report["summary"]["identity_critical_failures"] == ["follow-gaze"]
    assert report["summary"]["resolved_score"] == pytest.approx(
        report["summary"]["lower_bound"]
    )
    assert report["summary"]["upper_bound"] < 1.0


def test_invalid_substitution_assessment_is_rejected():
    profile, constraints, _, mapping = _inputs()
    with pytest.raises(RCLValidationError, match="fidelity must be in 0..1"):
        score_behavioral_continuity(
            profile,
            constraints,
            mapping,
            substitution_assessments={"follow-gaze": {"fidelity": 1.2}},
        )


def test_runtime_and_public_score_schemas_match():
    runtime = json.loads(
        (ROOT / "rcl" / "schemas" / "continuity-score-report.schema.json").read_text(
            encoding="utf-8"
        )
    )
    public = json.loads(
        (ROOT / "spec" / "schemas" / "continuity-score-report.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert runtime == public
