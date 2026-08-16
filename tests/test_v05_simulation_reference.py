import json
from pathlib import Path

from rcl.capability_path_reference_adapter import CapabilityPathReferenceAdapter
from rcl.profile import RCLProfile, validate_schema
from rcl.simulation_reference import run_simulation_reference_experiment


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v05_simulation_reference_experiment_passes():
    base = _root() / "examples" / "v0.5-sim"
    profile = RCLProfile.open(base / "robot-a")

    report = run_simulation_reference_experiment(
        profile,
        _read(base / "robot-b.embodiment.json"),
        _read(base / "robot-a.intent-series.json"),
        _read(base / "robot-b.intent-series.json"),
        CapabilityPathReferenceAdapter(),
        behavior_id="safety.pre_sit_clearance_check",
        expected_target_path_id="direct_clearance",
        created_at="2026-08-16T04:00:00Z",
    )

    validate_schema(report, "simulation-reference-report")
    assert report["assertions"]["experiment_passed"] is True
    assert report["source"]["observed_success_rate"] == 1.0
    assert report["target"]["observed_success_rate"] == 1.0
    assert report["source"]["observed_strategy_ids"] == [
        "source.rear_attention_clearance"
    ]
    assert report["target"]["observed_strategy_ids"] == [
        "target.direct_clearance_state"
    ]
    assert report["migration"]["selected_capability_path_id"] == "direct_clearance"
    assert report["migration"]["target_strategy"] == "target.direct_clearance_state"
    assert report["migration"]["intent_status"] == "preserved"
    assert report["migration"]["expression_status"] == "unsupported"
    assert report["assertions"]["strategies_differ"] is True
    assert report["assertions"]["target_strategy_observed"] is True


def test_simulation_reference_schema_is_published_with_runtime_parity():
    root = _root()
    runtime = _read(root / "rcl" / "schemas" / "simulation-reference-report.schema.json")
    published = _read(root / "spec" / "schemas" / "simulation-reference-report.schema.json")
    assert runtime == published
