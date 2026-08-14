from pathlib import Path

from rcl.profile import RCLProfile, RCL_VERSION


def test_example_validates():
    root = Path(__file__).resolve().parents[1]
    profile = RCLProfile(root / "examples" / "mobile-base")
    profile.validate(require_manifest=False)
    assert profile.summary()["robot_id"] == "RCL-DEMO-ROVER-A"
    assert profile.summary()["rcl_version"] == RCL_VERSION == "0.2"


def test_round_trip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = root / "examples" / "mobile-base"
    output = tmp_path / "demo.rcl"
    RCLProfile.pack(source, output, "RCL-DEMO-PROFILE-002", "2026-08-14T00:00:00Z")
    restored = RCLProfile.open(output)
    assert restored.summary()["behavior_count"] == 2
    assert restored.load("manifest.json")["rcl_version"] == "0.2"
