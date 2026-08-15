import json
import shutil
from pathlib import Path

from rcl.profile import PAYLOADS, RCLProfile
from rcl.profile_diff import diff_profiles


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _copy_profile(source: Path, target: Path) -> RCLProfile:
    target.mkdir()
    for name in PAYLOADS:
        shutil.copyfile(source / name, target / name)
    return RCLProfile.open(target)


def test_profile_diff_exposes_legacy_to_capability_paths_change(tmp_path):
    source = _root() / "examples" / "intent" / "sit-assistant-v1"
    before = _copy_profile(source, tmp_path / "before")
    _copy_profile(source, tmp_path / "after")

    behavior_path = tmp_path / "after" / "behavior.json"
    payload = json.loads(behavior_path.read_text(encoding="utf-8"))
    behavior = next(
        item for item in payload["behaviors"]
        if item["behavior_id"] == "safety.pre_sit_clearance_check"
    )
    behavior["intent"].pop("required_capabilities")
    behavior["intent"]["capability_paths"] = [
        {
            "path_id": "direct_clearance",
            "all_of": ["perception.sitting_area_clearance"],
        },
        {
            "path_id": "external_seat_state",
            "one_of": [
                "x.demo.external_seat_clearance",
                "x.demo.networked_seat_clearance",
            ],
        },
    ]
    behavior_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    after = RCLProfile.open(tmp_path / "after")

    report = diff_profiles(before, after)
    change = next(
        item for item in report["behavior_changes"]
        if item["behavior_id"] == "safety.pre_sit_clearance_check"
    )
    fields = {item["field"]: item for item in change["field_changes"]}
    assert fields["intent.required_capabilities"]["change_type"] == "removed"
    assert fields["intent.capability_paths"]["change_type"] == "added"
    assert fields["intent.capability_paths"]["after"][1]["path_id"] == "external_seat_state"
