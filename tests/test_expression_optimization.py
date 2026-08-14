import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from rcl.expression_history import (
    NULL_EXPRESSION_SHA256,
    expression_sha256,
    validate_behavior_expression_history_metadata,
)
from rcl.expression_optimization import (
    apply_expression_optimization,
    preview_expression_optimization,
)
from rcl.profile import RCLProfile, RCLValidationError
from rcl.profile_diff import diff_profiles


BEHAVIOR_ID = "safety.pre_sit_clearance_check"


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    return RCLProfile.open(_root() / "examples" / "intent" / "sit-assistant-v1")


def _behavior(profile: RCLProfile) -> dict:
    return next(
        item for item in profile.load("behavior.json")["behaviors"]
        if item["behavior_id"] == BEHAVIOR_ID
    )


def _candidate(
    profile: RCLProfile,
    *,
    action: str = "remove",
    replacement=None,
    candidate_id: str = "expr-opt-candidate-001",
    created_at: str = "2026-08-15T02:00:00+09:00",
) -> dict:
    expression = _behavior(profile)["expression"]
    return {
        "candidate_version": "0.1",
        "candidate_id": candidate_id,
        "created_at": created_at,
        "behavior_id": BEHAVIOR_ID,
        "current_expression_sha256": expression_sha256(expression),
        "action": action,
        "reason": "Target-native sensing satisfies the functional goal before the legacy gesture.",
        "evidence_refs": ["intent-success://session-42"],
        "replacement_expression": replacement,
    }


def _simplified_expression(profile: RCLProfile) -> dict:
    expression = copy.deepcopy(_behavior(profile)["expression"])
    expression["expression_id"] = "observation.subtle_rearward_glance"
    expression["description"] = "A smaller rearward glance that preserves the familiar manner with less motion."
    return expression


def _strip_expression_fields(behavior: dict) -> dict:
    result = copy.deepcopy(behavior)
    result.pop("expression", None)
    result.pop("expression_history", None)
    return result


def test_null_expression_digest_is_canonical_json_null():
    assert NULL_EXPRESSION_SHA256 == hashlib.sha256(b"null").hexdigest()
    assert expression_sha256(None) == NULL_EXPRESSION_SHA256


def test_preview_is_deterministic_and_non_mutating():
    profile = _profile()
    before = copy.deepcopy(_behavior(profile))
    candidate = _candidate(profile)

    first = preview_expression_optimization(
        profile,
        candidate,
        BEHAVIOR_ID,
        approved_at="2026-08-15T03:00:00+09:00",
        approved_by="local-user",
    )
    second = preview_expression_optimization(
        profile,
        candidate,
        BEHAVIOR_ID,
        approved_at="2026-08-15T03:00:00+09:00",
        approved_by="local-user",
    )

    assert first == second
    assert first["candidate"]["action"] == "remove"
    assert first["after_expression"] is None
    assert first["history_entry"]["expression_snapshot"] == before["expression"]
    assert first["history_entry"]["to_expression_sha256"] == NULL_EXPRESSION_SHA256
    assert _behavior(profile) == before


def test_remove_creates_new_snapshot_and_preserves_full_expression_history(tmp_path):
    profile = _profile()
    before = copy.deepcopy(_behavior(profile))
    source_bytes = {
        name: (profile.root / name).read_bytes()
        for name in ("identity.json", "preferences.json", "behavior.json", "skills.json", "embodiment.json")
    }
    candidate = _candidate(profile)
    output = tmp_path / "removed"

    result = apply_expression_optimization(
        profile,
        candidate,
        BEHAVIOR_ID,
        output,
        approved_at="2026-08-15T03:00:00+09:00",
        approved_by="local-user",
    )

    assert result["action"] == "remove"
    assert result["source_unchanged"] is True
    assert result["output_valid"] is True
    after_profile = RCLProfile.open(output)
    after = _behavior(after_profile)
    assert "expression" not in after
    assert len(after["expression_history"]) == 1
    entry = after["expression_history"][0]
    assert entry["action"] == "remove"
    assert entry["expression_snapshot"] == before["expression"]
    assert entry["from_expression_sha256"] == expression_sha256(before["expression"])
    assert entry["to_expression_sha256"] == NULL_EXPRESSION_SHA256
    assert _strip_expression_fields(after) == _strip_expression_fields(before)
    for name, data in source_bytes.items():
        assert (profile.root / name).read_bytes() == data

    diff = diff_profiles(profile, after_profile)
    change = diff["behavior_changes"][0]
    fields = {item["field"] for item in change["field_changes"]}
    assert "expression.expression_id" in fields
    assert "expression_history" in fields
    assert change["parameter_changes"] == []


def test_simplify_replaces_active_expression_and_appends_previous_snapshot(tmp_path):
    profile = _profile()
    before = copy.deepcopy(_behavior(profile))
    replacement = _simplified_expression(profile)
    candidate = _candidate(profile, action="simplify", replacement=replacement)
    output = tmp_path / "simplified"

    apply_expression_optimization(
        profile,
        candidate,
        BEHAVIOR_ID,
        output,
        approved_at="2026-08-15T03:00:00+09:00",
    )

    after = _behavior(RCLProfile.open(output))
    assert after["expression"] == replacement
    assert after["expression_history"][0]["expression_snapshot"] == before["expression"]
    assert after["expression_history"][0]["to_expression_sha256"] == expression_sha256(replacement)
    assert _strip_expression_fields(after) == _strip_expression_fields(before)


def test_simplify_then_remove_forms_continuous_history_chain(tmp_path):
    source = _profile()
    replacement = _simplified_expression(source)
    first_candidate = _candidate(
        source,
        action="simplify",
        replacement=replacement,
        candidate_id="expr-opt-candidate-simplify",
    )
    first_output = tmp_path / "step-one"
    apply_expression_optimization(
        source,
        first_candidate,
        BEHAVIOR_ID,
        first_output,
        approved_at="2026-08-15T03:00:00+09:00",
    )

    step_one = RCLProfile.open(first_output)
    second_candidate = _candidate(
        step_one,
        action="remove",
        candidate_id="expr-opt-candidate-remove",
        created_at="2026-08-15T03:10:00+09:00",
    )
    second_output = tmp_path / "step-two"
    apply_expression_optimization(
        step_one,
        second_candidate,
        BEHAVIOR_ID,
        second_output,
        approved_at="2026-08-15T03:20:00+09:00",
    )

    final_behavior = _behavior(RCLProfile.open(second_output))
    assert "expression" not in final_behavior
    history = final_behavior["expression_history"]
    assert len(history) == 2
    assert history[0]["action"] == "simplify"
    assert history[1]["action"] == "remove"
    assert history[0]["to_expression_sha256"] == history[1]["from_expression_sha256"]
    assert history[1]["to_expression_sha256"] == NULL_EXPRESSION_SHA256
    assert history[0]["expression_snapshot"]["expression_id"] == "observation.brief_rearward_check"
    assert history[1]["expression_snapshot"] == replacement


def test_stale_candidate_is_rejected():
    profile = _profile()
    candidate = _candidate(profile)
    candidate["current_expression_sha256"] = "0" * 64
    with pytest.raises(RCLValidationError, match="stale"):
        preview_expression_optimization(
            profile,
            candidate,
            BEHAVIOR_ID,
            approved_at="2026-08-15T03:00:00+09:00",
        )


def test_semantic_noop_simplify_is_rejected():
    profile = _profile()
    replacement = copy.deepcopy(_behavior(profile)["expression"])
    candidate = _candidate(profile, action="simplify", replacement=replacement)
    with pytest.raises(RCLValidationError, match="semantic no-op"):
        preview_expression_optimization(
            profile,
            candidate,
            BEHAVIOR_ID,
            approved_at="2026-08-15T03:00:00+09:00",
        )


def test_remove_with_replacement_is_rejected():
    profile = _profile()
    candidate = _candidate(profile, replacement=_simplified_expression(profile))
    with pytest.raises(RCLValidationError, match="replacement_expression=null"):
        preview_expression_optimization(
            profile,
            candidate,
            BEHAVIOR_ID,
            approved_at="2026-08-15T03:00:00+09:00",
        )


def test_approval_time_cannot_precede_candidate():
    profile = _profile()
    candidate = _candidate(profile)
    with pytest.raises(RCLValidationError, match="cannot precede"):
        preview_expression_optimization(
            profile,
            candidate,
            BEHAVIOR_ID,
            approved_at="2026-08-15T01:00:00+09:00",
        )


def test_existing_output_and_nested_output_are_rejected(tmp_path):
    profile = _profile()
    candidate = _candidate(profile)
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(RCLValidationError, match="already exists"):
        apply_expression_optimization(
            profile,
            candidate,
            BEHAVIOR_ID,
            existing,
            approved_at="2026-08-15T03:00:00+09:00",
        )

    nested = profile.root / "nested-output"
    with pytest.raises(RCLValidationError, match="inside the source"):
        apply_expression_optimization(
            profile,
            candidate,
            BEHAVIOR_ID,
            nested,
            approved_at="2026-08-15T03:00:00+09:00",
        )


def test_history_snapshot_tampering_is_detected(tmp_path):
    profile = _profile()
    candidate = _candidate(profile, action="simplify", replacement=_simplified_expression(profile))
    output = tmp_path / "simplified"
    apply_expression_optimization(
        profile,
        candidate,
        BEHAVIOR_ID,
        output,
        approved_at="2026-08-15T03:00:00+09:00",
    )
    payload = RCLProfile.open(output).load("behavior.json")
    behavior = next(item for item in payload["behaviors"] if item["behavior_id"] == BEHAVIOR_ID)
    behavior["expression_history"][0]["expression_snapshot"]["description"] = "tampered"
    with pytest.raises(RCLValidationError, match="does not match snapshot"):
        validate_behavior_expression_history_metadata(payload)


def test_temporal_style_and_source_artifacts_survive_removal_history(tmp_path):
    source_dir = tmp_path / "source-with-timing"
    shutil.copytree(_root() / "examples" / "intent" / "sit-assistant-v1", source_dir)
    payload_path = source_dir / "behavior.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    behavior = next(item for item in payload["behaviors"] if item["behavior_id"] == BEHAVIOR_ID)
    behavior["expression"]["temporal_style"] = {
        "tempo": "natural",
        "dwell": "brief",
        "transition": "smooth",
        "timing_policy": "naturalize",
        "legacy_significance": "recognized",
        "source_timing_observation": {
            "motion_duration_ms": 1400,
            "dwell_duration_ms": 220,
            "return_duration_ms": 1350,
            "normative": False,
        },
        "source_artifacts": [
            {"artifact": "actuator_speed_limit", "effect": "slower_than_intended"},
            {"artifact": "wiring_constraint", "effect": "slower_than_intended"},
        ],
    }
    payload_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    profile = RCLProfile.open(source_dir)
    original_style = copy.deepcopy(_behavior(profile)["expression"]["temporal_style"])
    candidate = _candidate(profile)
    output = tmp_path / "timing-removed"

    apply_expression_optimization(
        profile,
        candidate,
        BEHAVIOR_ID,
        output,
        approved_at="2026-08-15T03:00:00+09:00",
    )
    history_snapshot = _behavior(RCLProfile.open(output))["expression_history"][0]["expression_snapshot"]
    assert history_snapshot["temporal_style"] == original_style


def test_runtime_and_public_expression_optimization_schemas_match():
    root = _root()
    pairs = [
        (
            root / "rcl" / "schemas" / "behavior.schema.json",
            root / "spec" / "schemas" / "v0.4" / "behavior.schema.json",
        ),
        (
            root / "rcl" / "schemas" / "expression-optimization-candidate.schema.json",
            root / "spec" / "schemas" / "expression-optimization-candidate.schema.json",
        ),
        (
            root / "rcl" / "schemas" / "expression-optimization-patch.schema.json",
            root / "spec" / "schemas" / "expression-optimization-patch.schema.json",
        ),
        (
            root / "rcl" / "schemas" / "expression-optimization-result.schema.json",
            root / "spec" / "schemas" / "expression-optimization-result.schema.json",
        ),
    ]
    for runtime_path, public_path in pairs:
        assert json.loads(runtime_path.read_text(encoding="utf-8")) == json.loads(
            public_path.read_text(encoding="utf-8")
        )
