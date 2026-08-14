import copy
import json
import math
import sys
from pathlib import Path

from rcl.cli import main as rcl_main
from rcl.profile import RCLProfile, validate_schema
from rcl.session_evaluation import (
    confidence_interval_95,
    evaluate_repeated_sessions,
    t95_critical,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profile() -> RCLProfile:
    profile = RCLProfile(_root() / "examples" / "mobile-base")
    profile.validate(require_manifest=False)
    return profile


def _trial_payload(
    robot_id: str,
    session_id: str,
    distance,
    *,
    environment_id: str = "demo-lab-a-layout-01",
    protocol_version: str = "0.1",
):
    return {
        "trial_observation_version": "0.2",
        "robot_id": robot_id,
        "embodiment_id": f"{robot_id.lower()}-embodiment",
        "captured_at": "2026-08-14T03:10:00Z",
        "experiment": {
            "protocol": {
                "protocol_id": "rcl.person_following.baseline",
                "protocol_version": protocol_version,
                "comparison_fields": [
                    "task_id",
                    "environment_id",
                    "subject_ref",
                    "start_condition_id",
                ],
            },
            "context": {
                "session_id": session_id,
                "task_id": "follow-person-straight-5m",
                "environment_id": environment_id,
                "subject_ref": "subject-demo-01",
                "start_condition_id": "stationary-2m-behind-subject",
                "software_ref": f"{robot_id.lower()}-software@1",
            },
        },
        "behavior_trials": [
            {
                "behavior_id": "navigation.follow_person",
                "metrics": {"following_distance_m": list(distance)},
            }
        ],
    }


def _pair(session_id: str, target_distance, *, environment_id="demo-lab-a-layout-01"):
    return {
        "session_id": session_id,
        "source_trials": _trial_payload(
            "A", f"a-{session_id}", [1.4] * 5, environment_id=environment_id
        ),
        "target_trials": _trial_payload(
            "B", f"b-{session_id}", target_distance, environment_id=environment_id
        ),
    }


def _reference_pairs():
    root = _root()
    manifest_path = root / "examples" / "sessions" / "demo-rover-a-b.sessions.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    pairs = []
    for item in manifest["sessions"]:
        pairs.append(
            {
                "session_id": item["session_id"],
                "source_trials": json.loads((base / item["source_trials"]).read_text(encoding="utf-8")),
                "target_trials": json.loads((base / item["target_trials"]).read_text(encoding="utf-8")),
            }
        )
    return manifest, pairs


def test_reference_three_sessions_have_zero_uncertainty_at_full_score():
    manifest, pairs = _reference_pairs()
    report = evaluate_repeated_sessions(
        _profile(),
        pairs,
        min_sessions=manifest["min_sessions"],
        created_at="2026-08-17T00:00:00Z",
    )

    validate_schema(report, "session-evaluation-report")
    assert report["evaluation_success"] is True
    assert report["status"] == "estimated"
    assert report["total_session_count"] == 3
    assert report["scorable_session_count"] == 3
    assert report["successful_session_count"] == 3
    assert report["failed_session_count"] == 0
    assert report["mean_score"] == 100.0
    assert report["score_std"] == 0.0
    assert report["confidence_interval_95"]["low"] == 100.0
    assert report["confidence_interval_95"]["high"] == 100.0
    assert report["confidence_interval_95"]["critical_value"] == 4.303
    assert report["series_comparison"]["compatible"] is True


def test_student_t_95_interval_uses_small_sample_critical_value():
    assert t95_critical(2) == 4.303
    ci = confidence_interval_95([100.0, 70.0, 50.0], lower_bound=0.0, upper_bound=100.0)
    assert ci["critical_value"] == 4.303
    assert ci["half_width"] > 60
    assert ci["low"] < 15
    assert ci["high"] == 100.0


def test_high_between_session_variance_widens_confidence_interval():
    pairs = [
        _pair("day-1", [1.4] * 5),
        _pair("day-2", [1.2, 1.2, 1.4, 1.6, 1.6]),
        _pair("day-3", [1.2, 1.2, 1.2, 1.6, 1.6]),
    ]

    report = evaluate_repeated_sessions(_profile(), pairs)

    assert report["evaluation_success"] is True
    assert report["status"] == "estimated"
    assert math.isclose(report["mean_score"], 73.333333, abs_tol=1e-6)
    assert report["score_std"] > 20
    assert report["confidence_interval_95"]["half_width"] > 60
    metric = next(
        item for item in report["metric_summaries"] if item["metric_id"] == "following_distance"
    )
    assert metric["session_count"] == 3
    assert math.isclose(metric["mean_similarity"], 0.733333, abs_tol=1e-6)
    assert metric["confidence_interval_95"] is not None


def test_context_mismatch_session_is_visible_and_blocks_success():
    good1 = _pair("day-1", [1.4] * 5)
    good2 = _pair("day-2", [1.4] * 5)
    bad = _pair("day-3", [1.4] * 5)
    bad["target_trials"]["experiment"]["context"]["environment_id"] = "different-lab"

    report = evaluate_repeated_sessions(_profile(), [good1, good2, bad])

    assert report["evaluation_success"] is False
    assert report["status"] == "session_failures"
    assert report["scorable_session_count"] == 2
    assert report["failed_session_count"] == 1
    assert report["context_mismatch_session_ids"] == ["day-3"]
    assert report["confidence_interval_95"] is None
    day3 = next(item for item in report["session_results"] if item["session_id"] == "day-3")
    assert day3["score"] is None
    assert day3["context_compatible"] is False


def test_required_metric_failure_is_included_but_not_hidden_by_average():
    pairs = [
        _pair("day-1", [1.4] * 5),
        _pair("day-2", [1.4] * 5),
        _pair("day-3", [1.8] * 5),
    ]

    report = evaluate_repeated_sessions(_profile(), pairs)

    assert report["scorable_session_count"] == 3
    assert report["failed_session_count"] == 1
    assert report["evaluation_success"] is False
    assert report["status"] == "session_failures"
    assert math.isclose(report["mean_score"], 66.666667, abs_tol=1e-6)
    assert report["confidence_interval_95"] is not None
    assert "day-3" in report["failed_session_ids"]


def test_two_sessions_report_mean_but_not_confidence_interval():
    report = evaluate_repeated_sessions(
        _profile(),
        [_pair("day-1", [1.4] * 5), _pair("day-2", [1.4] * 5)],
    )

    assert report["mean_score"] == 100.0
    assert report["score_std"] == 0.0
    assert report["confidence_interval_95"] is None
    assert report["evaluation_success"] is False
    assert report["status"] == "insufficient_sessions"


def test_cross_session_context_change_blocks_series_aggregation():
    pairs = [
        _pair("day-1", [1.4] * 5),
        _pair("day-2", [1.4] * 5),
        _pair("day-3", [1.4] * 5, environment_id="another-lab"),
    ]

    report = evaluate_repeated_sessions(_profile(), pairs)

    assert report["series_comparison"]["compatible"] is False
    assert report["series_comparison"]["mismatches"]
    assert report["status"] == "series_mismatch"
    assert report["evaluation_success"] is False
    assert report["mean_score"] is None
    assert report["confidence_interval_95"] is None


def test_duplicate_session_id_is_rejected():
    pairs = [_pair("day-1", [1.4] * 5), _pair("day-1", [1.4] * 5)]
    try:
        evaluate_repeated_sessions(_profile(), pairs)
    except Exception as exc:
        assert "Duplicate session_id" in str(exc)
    else:
        raise AssertionError("duplicate session_id must be rejected")


def test_compare_sessions_cli_json(monkeypatch, capsys):
    root = _root()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "compare-sessions",
            str(root / "examples" / "mobile-base"),
            str(root / "examples" / "sessions" / "demo-rover-a-b.sessions.json"),
            "--json",
        ],
    )

    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_evaluation_version"] == "0.1"
    assert payload["method"] == "rcl.observed.session_mean_t95.v0.1"
    assert payload["confidence_level"] == 0.95
    assert payload["mean_score"] == 100.0
    assert payload["status"] == "estimated"
