import json
from importlib.resources import files
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_behavior_schema_public_runtime_parity():
    runtime = json.loads(files("rcl").joinpath("schemas", "behavior.schema.json").read_text(encoding="utf-8"))
    public = json.loads((_root() / "spec" / "schemas" / "v0.4" / "behavior.schema.json").read_text(encoding="utf-8"))
    assert public == runtime


def test_migration_report_schema_public_runtime_parity():
    runtime = json.loads(files("rcl").joinpath("schemas", "migration-report.schema.json").read_text(encoding="utf-8"))
    public = json.loads((_root() / "spec" / "schemas" / "v0.4" / "migration-report.schema.json").read_text(encoding="utf-8"))
    assert public == runtime
