import json
import sys

from rcl.adapter import BehaviorMigrationResult, RCLAdapter
from rcl.conformance import run_adapter_conformance
from rcl.conformance_cli import load_adapter, main
from rcl.profile import validate_schema
from rcl_ros2 import ROS2MobileBaseAdapter


class BrokenPreserveEverythingAdapter(RCLAdapter):
    adapter_id = "test.broken.preserve_everything"
    adapter_version = "0"

    def supports(self, target_embodiment):
        return target_embodiment.get("class") == "mobile_base"

    def translate_behavior(self, behavior, source_embodiment, target_embodiment):
        del source_embodiment, target_embodiment
        required = tuple(sorted(self.required_capabilities(behavior)))
        return BehaviorMigrationResult(
            behavior_id=behavior["behavior_id"],
            status="preserved",
            similarity=1.0,
            reason="Incorrectly claims every behavior is preserved.",
            mapped_parameters=dict(behavior.get("parameters", {})),
            required_capabilities=required,
            missing_capabilities=(),
        )


class UnknownReservedCapabilityAdapter(ROS2MobileBaseAdapter):
    adapter_id = "test.invalid.unknown_reserved_capability"

    def required_capabilities(self, behavior):
        return super().required_capabilities(behavior) | {"perception.telepathy"}


def test_ros2_reference_adapter_passes_conformance():
    report = run_adapter_conformance(ROS2MobileBaseAdapter())

    validate_schema(report, "conformance-report")
    assert report["passed"] is True
    assert report["compatibility_level"] == "RCL Migration Compatible"
    assert all(report["groups"].values())


def test_conformance_catches_adapter_that_hides_missing_capabilities():
    report = run_adapter_conformance(BrokenPreserveEverythingAdapter())

    assert report["passed"] is False
    assert report["compatibility_level"] is None
    assert report["groups"]["Profile"] is True
    assert report["groups"]["Adapter"] is True
    assert report["groups"]["Migration"] is False
    assert report["groups"]["Safety"] is False
    assert report["groups"]["Reporting"] is False

    failed = {item["check_id"] for item in report["checks"] if not item["passed"]}
    assert "degradation.visible" in failed
    assert "required_capability.honest_failure" in failed
    assert "required_capability.blocks_migration" in failed
    assert "migration_report.degradation_visible" in failed


def test_conformance_rejects_unknown_reserved_capability_vocabulary():
    report = run_adapter_conformance(UnknownReservedCapabilityAdapter())

    assert report["passed"] is False
    assert report["compatibility_level"] is None
    assert report["groups"]["Reporting"] is False

    failed = {
        item["check_id"]: item["message"]
        for item in report["checks"]
        if not item["passed"]
    }
    assert "migration_report.valid" in failed
    assert "reserved namespace" in failed["migration_report.valid"]


def test_adapter_loader_resolves_reference_class():
    adapter = load_adapter("rcl_ros2:ROS2MobileBaseAdapter")
    assert isinstance(adapter, ROS2MobileBaseAdapter)


def test_conformance_cli_json_output(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl-conformance",
            "test",
            "rcl_ros2:ROS2MobileBaseAdapter",
            "--json",
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["suite_id"] == "rcl.adapter.mobile_base.v0.3"
