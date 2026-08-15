import json
import sys
from pathlib import Path

from rcl import (
    CapabilityPathReferenceAdapter,
    INTENT_CONFORMANCE_COMPATIBILITY_LEVEL,
    INTENT_CONFORMANCE_SUITE_ID,
    run_intent_adapter_conformance,
)
from rcl.adapter import IntentMigrationResult
from rcl.capability_paths import declared_intent_capabilities
from rcl.conformance_cli import main
from rcl.intent_conformance import NO_PATH_TARGET
from rcl.profile import validate_schema


class FlattenAllPathsAdapter(CapabilityPathReferenceAdapter):
    adapter_id = "test.intent.flatten_all_paths"

    def translate_intent(self, behavior, source_embodiment, target_embodiment):
        intent = behavior.get("intent")
        if intent is None:
            return None
        required = declared_intent_capabilities(intent)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="unsupported",
                reason="Incorrectly flattens every alternative path into one AND-set.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )
        return super().translate_intent(behavior, source_embodiment, target_embodiment)


class LyingSelectedPathAdapter(CapabilityPathReferenceAdapter):
    adapter_id = "test.intent.lying_selected_path"

    def translate_intent(self, behavior, source_embodiment, target_embodiment):
        result = super().translate_intent(behavior, source_embodiment, target_embodiment)
        if result is None or result.status != "preserved":
            return result
        return IntentMigrationResult(
            goal_id=result.goal_id,
            status="preserved",
            reason="Incorrectly reports an unavailable path as selected.",
            target_strategy="target.fake_external_path",
            required_capabilities=result.required_capabilities,
            missing_capabilities=(),
            selected_capability_path_id="external_seat_state",
            capability_path_results=result.capability_path_results,
        )


class ExpressionSubstitutesForIntentAdapter(CapabilityPathReferenceAdapter):
    adapter_id = "test.intent.expression_substitution"

    def translate_intent(self, behavior, source_embodiment, target_embodiment):
        if target_embodiment.get("embodiment_id") == NO_PATH_TARGET["embodiment_id"]:
            intent = behavior.get("intent")
            if intent is None:
                return None
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="preserved",
                reason="Incorrectly treats reproducible legacy expression as functional Intent satisfaction.",
                target_strategy="target.legacy_expression_only",
                required_capabilities=("perception.directional_attention",),
                missing_capabilities=(),
                selected_capability_path_id="direct_clearance",
                capability_path_results=(),
            )
        return super().translate_intent(behavior, source_embodiment, target_embodiment)


def test_capability_path_reference_adapter_passes_intent_conformance():
    report = run_intent_adapter_conformance(CapabilityPathReferenceAdapter())

    validate_schema(report, "intent-conformance-report")
    assert report["passed"] is True
    assert report["suite_id"] == INTENT_CONFORMANCE_SUITE_ID
    assert report["compatibility_level"] == INTENT_CONFORMANCE_COMPATIBILITY_LEVEL
    assert all(report["groups"].values())


def test_intent_conformance_catches_flattened_alternative_paths():
    report = run_intent_adapter_conformance(FlattenAllPathsAdapter())

    assert report["passed"] is False
    assert report["compatibility_level"] is None
    failed = {item["check_id"] for item in report["checks"] if not item["passed"]}
    assert "direct.intent_preserved" in failed
    assert "alternate.intent_preserved" in failed
    assert "alternate.not_flattened" in failed


def test_intent_conformance_catches_false_selected_path():
    report = run_intent_adapter_conformance(LyingSelectedPathAdapter())

    assert report["passed"] is False
    failed = {item["check_id"] for item in report["checks"] if not item["passed"]}
    assert "direct.selected_path_truthful" in failed
    assert "direct.path_diagnostics_complete" in failed


def test_intent_conformance_catches_expression_substitution():
    report = run_intent_adapter_conformance(ExpressionSubstitutesForIntentAdapter())

    assert report["passed"] is False
    failed = {item["check_id"] for item in report["checks"] if not item["passed"]}
    assert "no_path.honest_failure" in failed
    assert "expression.not_intent_substitute" in failed
    assert "required_intent.blocks_migration" in failed


def test_intent_conformance_schema_public_copy_matches_runtime():
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "rcl" / "schemas" / "intent-conformance-report.schema.json").read_text(encoding="utf-8")
    public = (root / "spec" / "schemas" / "intent-conformance-report.schema.json").read_text(encoding="utf-8")
    assert json.loads(runtime) == json.loads(public)


def test_intent_conformance_cli_json(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl-conformance",
            "intent",
            "rcl:CapabilityPathReferenceAdapter",
            "--json",
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["suite_id"] == "rcl.adapter.intent.v0.4"
    assert payload["compatibility_level"] == "RCL Intent Migration Compatible"
