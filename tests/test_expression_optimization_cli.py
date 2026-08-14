import json
import subprocess
from pathlib import Path

from rcl.expression_history import expression_sha256
from rcl.profile import RCLProfile


BEHAVIOR_ID = "safety.pre_sit_clearance_check"


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidate(profile: RCLProfile) -> dict:
    behavior = next(
        item for item in profile.load("behavior.json")["behaviors"]
        if item["behavior_id"] == BEHAVIOR_ID
    )
    return {
        "candidate_version": "0.1",
        "candidate_id": "cli-expression-remove-001",
        "created_at": "2026-08-15T02:00:00+09:00",
        "behavior_id": BEHAVIOR_ID,
        "current_expression_sha256": expression_sha256(behavior["expression"]),
        "action": "remove",
        "reason": "Explicitly remove the visible legacy gesture after review.",
        "evidence_refs": ["intent-success://cli-demo"],
        "replacement_expression": None,
    }


def test_installed_cli_preview_and_apply(tmp_path):
    source = _root() / "examples" / "intent" / "sit-assistant-v1"
    profile = RCLProfile.open(source)
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(_candidate(profile), indent=2) + "\n", encoding="utf-8")
    patch_path = tmp_path / "patch.json"

    preview = subprocess.run(
        [
            "rcl",
            "optimize-expression",
            "preview",
            str(source),
            str(candidate_path),
            BEHAVIOR_ID,
            "--approved-at",
            "2026-08-15T03:00:00+09:00",
            "--approved-by",
            "cli-user",
            "--output",
            str(patch_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert preview.returncode == 0, preview.stdout + preview.stderr
    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    assert patch["candidate"]["action"] == "remove"
    assert patch["after_expression"] is None

    output = tmp_path / "optimized"
    apply = subprocess.run(
        [
            "rcl",
            "optimize-expression",
            "apply",
            str(source),
            str(candidate_path),
            BEHAVIOR_ID,
            str(output),
            "--approved-at",
            "2026-08-15T03:00:00+09:00",
            "--approved-by",
            "cli-user",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert apply.returncode == 0, apply.stdout + apply.stderr
    result = json.loads(apply.stdout)
    assert result["action"] == "remove"
    assert result["output_valid"] is True
    optimized = RCLProfile.open(output)
    behavior = next(
        item for item in optimized.load("behavior.json")["behaviors"]
        if item["behavior_id"] == BEHAVIOR_ID
    )
    assert "expression" not in behavior
    assert len(behavior["expression_history"]) == 1
