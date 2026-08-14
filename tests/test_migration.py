import json
import shutil
from pathlib import Path

import pytest

from rcl.capabilities import CapabilityValidationError
from rcl.example_adapter import ExampleMobileBaseAdapter
from rcl.migration import migrate_profile
from rcl.profile import RCLProfile, validate_schema


def _fixtures():
    root = Path(__file__).resolve().parents[1]
    profile = RCLProfile(root / "examples" / "mobile-base")
    profile.validate(require_manifest=False)
    target = json.loads(
        (root / "examples" / "targets" / "demo-rover-b.embodiment.json").read_text(encoding="utf-8")
    )
    return root, profile, target


def test_reference_migration_score():
    _, profile, target = _fixtures()
    report = migrate_profile(
        profile,
        target,
        ExampleMobileBaseAdapter(),
        created_at="2026-08-14T00:00:00Z",
    )
    validate_schema(report, "migration-report")
    assert report["continuity"]["score"] == 88.33
    assert report["continuity"]["migration_success"] is True
    assert [item["status"] for item in report["behavior_results"]] == [
        "preserved",
        "approximated",
    ]


def test_required_failure_overrides_score(tmp_path):
    root, _, target = _fixtures()
    copied = tmp_path / "profile"
    shutil.copytree(root / "examples" / "mobile-base", copied)

    behavior_path = copied / "behavior.json"
    behavior = json.loads(behavior_path.read_text(encoding="utf-8"))
    behavior["behaviors"][0]["preservation"]["priority"] = "required"
    behavior_path.write_text(json.dumps(behavior, indent=2) + "\n", encoding="utf-8")

    target["capabilities"].remove("perception.person_tracking")
    report = migrate_profile(
        RCLProfile(copied),
        target,
        ExampleMobileBaseAdapter(),
        created_at="2026-08-14T00:00:00Z",
    )

    assert report["continuity"]["migration_success"] is False
    assert report["continuity"]["required_failures"] == ["navigation.follow_person"]
    assert report["behavior_results"][0]["status"] == "unsupported"


def test_migration_allows_explicit_extension_capability():
    _, profile, target = _fixtures()
    target["capabilities"].append("x.acme.experimental_range_fusion")

    report = migrate_profile(
        profile,
        target,
        ExampleMobileBaseAdapter(),
        created_at="2026-08-14T00:00:00Z",
    )

    assert report["continuity"]["migration_success"] is True


def test_migration_rejects_unknown_reserved_capability():
    _, profile, target = _fixtures()
    target["capabilities"].append("perception.telepathy")

    with pytest.raises(CapabilityValidationError, match="reserved namespace"):
        migrate_profile(
            profile,
            target,
            ExampleMobileBaseAdapter(),
            created_at="2026-08-14T00:00:00Z",
        )
