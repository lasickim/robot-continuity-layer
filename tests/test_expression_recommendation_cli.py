import json
import subprocess
from pathlib import Path

from rcl.intent_reference_adapter import IntentReferenceAdapter
from rcl.intent_success_evaluation import evaluate_observed_intent_success
from rcl.migration import migrate_profile
from rcl.profile import RCLProfile


SIT = "safety.pre_sit_clearance_check"
HANDOVER = "interaction.present_handover"


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source() -> Path:
    return _root() / "examples" / "intent" / "sit-assistant-v1"


def _target() -> dict:
    return json.loads(
        (
            _root()
            / "examples"
            / "targets"
            / "intent-demo-v2-expressive.embodiment.json"
        ).read_text(encoding="utf-8")
    )


def _reports():
    profile = RCLProfile.open(_source())
    target = _target()
    migration = migrate_profile(
        profile,
        target,
        IntentReferenceAdapter(),
        created_at="2026-08-15T03:35:00+09:00",
    )
    observations = {
        "intent_observation_version": "0.1",
        "robot_id": "RCL-INTENT-DEMO-V2",
        "embodiment_id": target["embodiment_id"],
        "captured_at": "2026-08-15T03:36:00+09:00",
        "intent_observations": [
            {
                "observation_id": "expr-rec-cli-sit",
                "behavior_id": SIT,
                "trigger": "activity.before_sit_down",
                "trigger_state": "observed",
                "success_condition": "state.sitting_area_clear",
                "success_state": "satisfied",
                "strategy_id": "direct_rear_clearance_sensing",
                "evidence_refs": ["observation://cli/sit"],
            },
            {
                "observation_id": "expr-rec-cli-handover",
                "behavior_id": HANDOVER,
                "trigger": "interaction.before_handover_release",
                "trigger_state": "observed",
                "success_condition": "state.handover_orientation_acceptable",
                "success_state": "satisfied",
                "strategy_id": "target_native_handover_orientation",
                "evidence_refs": ["observation://cli/handover"],
            },
        ],
    }
    success = evaluate_observed_intent_success(
        profile,
        observations,
        created_at="2026-08-15T03:37:00+09:00",
    )
    return migration, success


def test_installed_cli_json_report(tmp_path):
    migration, success = _reports()
    migration_path = tmp_path / "migration.json"
    success_path = tmp_path / "intent-success.json"
    migration_path.write_text(json.dumps(migration, indent=2) + "\n", encoding="utf-8")
    success_path.write_text(json.dumps(success, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "rcl",
            "expression-recommendations",
            str(_source()),
            str(migration_path),
            str(success_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["non_mutating"] is True
    assert report["redundancy_proven"] is False
    decisions = {item["behavior_id"]: item["decision"] for item in report["recommendations"]}
    assert decisions[SIT] == "review_simplification"
    assert decisions[HANDOVER] == "retain"


def test_installed_cli_output_file(tmp_path):
    migration, success = _reports()
    migration_path = tmp_path / "migration.json"
    success_path = tmp_path / "intent-success.json"
    output_path = tmp_path / "recommendations.json"
    migration_path.write_text(json.dumps(migration, indent=2) + "\n", encoding="utf-8")
    success_path.write_text(json.dumps(success, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "rcl",
            "expression-recommendations",
            str(_source()),
            str(migration_path),
            str(success_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert output_path.exists()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["summary"]["total"] == 2
    assert report["non_mutating"] is True
    assert report["redundancy_proven"] is False
