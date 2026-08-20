from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcl.behavior_compiler import compile_behavior_preserving_plan
from rcl.compatibility_mapping import map_behavioral_compatibility
from rcl.continuity_score import score_behavioral_continuity
from rcl.profile import RCLValidationError

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "v0.5-continuity"


def _read(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _reports(substitution_assessments=None):
    profile = _read("robot-a.continuity-profile.json")
    constraints = _read("identity-constraints.example.json")
    target = _read("robot-b.capability-manifest.json")
    mapping = map_behavioral_compatibility(profile, constraints, target, created_at="2026-08-20T10:00:00Z")
    score = score_behavioral_continuity(
        profile,
        constraints,
        mapping,
        substitution_assessments=substitution_assessments,
        created_at="2026-08-20T11:00:00Z",
    )
    return mapping, score


def test_reference_plan_requires_review_for_unresolved_substitute():
    mapping, score = _reports()
    plan = compile_behavior_preserving_plan(mapping, score, created_at="2026-08-20T12:00:00Z")
    assert plan["summary"]["plan_status"] == "REVIEW_REQUIRED"
    assert plan["summary"]["status_counts"] == {"READY": 6, "REVIEW_REQUIRED": 1, "BLOCKED": 0}
    gaze = next(x for x in plan["instructions"] if x["dimension"] == "gaze_before_move")
    assert gaze["execution_status"] == "REVIEW_REQUIRED"
    assert gaze["substitution_strategy"] == "body_yaw_attention_cue"


def test_evidence_resolved_substitute_becomes_ready():
    mapping, score = _reports({"follow-gaze": {"fidelity": 0.8, "evidence_refs": ["physical://run-01"]}})
    plan = compile_behavior_preserving_plan(mapping, score)
    assert plan["summary"]["plan_status"] == "READY"
    assert plan["summary"]["resolved_continuity_score"] == pytest.approx(0.9551401022)
    gaze = next(x for x in plan["instructions"] if x["dimension"] == "gaze_before_move")
    assert gaze["execution_status"] == "READY"
    assert gaze["assessed_fidelity"] == 0.8


def test_identity_policy_failure_blocks_plan():
    mapping, score = _reports()
    gaze = next(x for x in mapping["mappings"] if x["dimension"] == "gaze_before_move")
    gaze["classification"] = "UNSUPPORTED"
    gaze["constraint_satisfied"] = False
    gaze["reason"] = "substitution_forbidden"
    score_item = next(x for x in score["trait_scores"] if x["dimension"] == "gaze_before_move")
    score_item["classification"] = "UNSUPPORTED"
    score_item["constraint_satisfied"] = False
    score_item["fidelity_lower"] = 0.0
    score_item["fidelity_upper"] = 0.0
    score_item["fidelity"] = 0.0
    plan = compile_behavior_preserving_plan(mapping, score)
    assert plan["summary"]["plan_status"] == "BLOCKED"
    assert plan["summary"]["identity_critical_blocked"] == ["follow-gaze"]


def test_input_linkage_mismatch_rejected():
    mapping, score = _reports()
    score["target_robot_id"] = "OTHER"
    with pytest.raises(RCLValidationError, match="target_robot_id"):
        compile_behavior_preserving_plan(mapping, score)


def test_runtime_public_schema_parity():
    runtime = json.loads((ROOT / "rcl/schemas/behavior-compiler-plan.schema.json").read_text(encoding="utf-8"))
    public = json.loads((ROOT / "spec/schemas/behavior-compiler-plan.schema.json").read_text(encoding="utf-8"))
    assert runtime == public
