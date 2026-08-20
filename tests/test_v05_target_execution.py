from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcl.behavior_compiler import compile_behavior_preserving_plan
from rcl.compatibility_mapping import map_behavioral_compatibility
from rcl.continuity_score import score_behavioral_continuity
from rcl.profile import RCLValidationError
from rcl.target_execution import build_execution_bundle, execute_target_bundle


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "v0.5-continuity"


def _read(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _plan(*, resolved_substitute: bool) -> dict:
    profile = _read("robot-a.continuity-profile.json")
    constraints = _read("identity-constraints.example.json")
    manifest = _read("robot-b.capability-manifest.json")
    mapping = map_behavioral_compatibility(profile, constraints, manifest)
    assessments = None
    if resolved_substitute:
        assessments = {
            "follow-gaze": {
                "fidelity": 0.8,
                "evidence_refs": ["test://substitute-assessment"],
            }
        }
    score = score_behavioral_continuity(
        profile, constraints, mapping, substitution_assessments=assessments
    )
    return compile_behavior_preserving_plan(mapping, score)


class FakeAdapter:
    def __init__(self) -> None:
        self.received: list[dict] = []

    def execute(self, instruction: dict) -> dict:
        self.received.append(instruction)
        return {
            "success": True,
            "evidence_refs": [f"test://executed/{instruction['constraint_id']}"],
        }


def test_review_required_plan_is_fail_closed():
    bundle = build_execution_bundle(
        _plan(resolved_substitute=False),
        adapter_id="fake-adapter",
        execution_id="exec-review",
    )
    assert bundle["dispatch_allowed"] is False
    assert bundle["instructions"] == []
    assert bundle["blocked_reasons"][0]["execution_status"] == "REVIEW_REQUIRED"
    with pytest.raises(RCLValidationError, match="blocked by compiler plan status"):
        execute_target_bundle(bundle, FakeAdapter())


def test_resolved_ready_plan_dispatches_all_instructions():
    bundle = build_execution_bundle(
        _plan(resolved_substitute=True),
        adapter_id="fake-adapter",
        execution_id="exec-ready",
    )
    adapter = FakeAdapter()
    report = execute_target_bundle(bundle, adapter)
    assert bundle["dispatch_allowed"] is True
    assert len(bundle["instructions"]) == 7
    assert len(adapter.received) == 7
    assert report["result"] == "SUCCESS"
    assert report["summary"] == {"attempted": 7, "succeeded": 7, "failed": 0}


def test_invalid_adapter_result_is_rejected():
    class BadAdapter:
        def execute(self, instruction: dict) -> dict:
            return {"success": "yes"}

    bundle = build_execution_bundle(
        _plan(resolved_substitute=True),
        adapter_id="bad-adapter",
        execution_id="exec-bad",
    )
    with pytest.raises(RCLValidationError, match="requires boolean success"):
        execute_target_bundle(bundle, BadAdapter())


def test_runtime_and_public_execution_schemas_match():
    for name in ("target-execution-bundle", "target-execution-report"):
        runtime = json.loads((ROOT / "rcl" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        public = json.loads((ROOT / "spec" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert runtime == public
