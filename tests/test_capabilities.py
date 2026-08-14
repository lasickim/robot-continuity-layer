import json
import sys
from pathlib import Path

import pytest

from rcl.capabilities import (
    CapabilityValidationError,
    classify_capability_id,
    get_capability,
    load_capability_registry,
    registered_capabilities,
    reserved_namespaces,
    validate_capability_id,
    validate_capability_set,
)
from rcl.cli import main as rcl_main
from rcl.profile import validate_schema


EXPECTED_INITIAL_CAPABILITIES = {
    "navigation.planar_velocity",
    "perception.person_tracking",
    "perception.forward_range",
    "perception.directional_attention",
    "perception.sitting_area_clearance",
    "manipulation.handover_orientation",
}


def test_registry_v01_validates_and_contains_initial_vocabulary():
    registry = load_capability_registry()

    validate_schema(registry, "capability-registry")
    assert registry["registry_version"] == "0.1"
    assert {item["capability_id"] for item in registered_capabilities()} == EXPECTED_INITIAL_CAPABILITIES
    assert {
        "navigation",
        "perception",
        "manipulation",
        "interaction",
        "mobility",
        "safety",
        "system",
    }.issubset(reserved_namespaces())


def test_published_spec_registry_matches_packaged_registry():
    root = Path(__file__).resolve().parents[1]
    published = json.loads(
        (root / "spec" / "capability-registry-v0.1.json").read_text(encoding="utf-8")
    )
    packaged = load_capability_registry()

    assert published == packaged
    validate_schema(published, "capability-registry")


def test_registered_standard_capability_is_classified_and_resolvable():
    result = classify_capability_id("perception.person_tracking")

    assert result.valid is True
    assert result.registered is True
    assert result.kind == "standard"
    assert result.namespace == "perception"
    assert get_capability("perception.person_tracking")["status"] == "experimental"


def test_extension_namespace_is_valid_but_not_registered():
    result = validate_capability_id("x.acme.stereo_person_tracking")

    assert result.valid is True
    assert result.registered is False
    assert result.kind == "extension"
    assert result.owner == "acme"


def test_unknown_capability_in_reserved_namespace_is_rejected():
    result = classify_capability_id("perception.telepathy")

    assert result.kind == "unknown_reserved"
    assert result.valid is False
    with pytest.raises(CapabilityValidationError, match="reserved namespace"):
        validate_capability_id("perception.telepathy")


def test_unreserved_and_malformed_ids_are_rejected():
    for capability_id in [
        "vision.person_tracking",
        "PersonTracking",
        "x.Acme.tracker",
        "x.acme",
        "perception.person-tracking",
    ]:
        with pytest.raises(CapabilityValidationError):
            validate_capability_id(capability_id)


def test_duplicate_capability_set_is_rejected():
    with pytest.raises(CapabilityValidationError, match="duplicate"):
        validate_capability_set(
            ["navigation.planar_velocity", "navigation.planar_velocity"]
        )


def test_extension_can_be_disallowed_in_standard_only_context():
    with pytest.raises(CapabilityValidationError, match="not allowed"):
        validate_capability_id(
            "x.acme.stereo_person_tracking",
            allow_extensions=False,
        )


def test_capability_cli_list_and_validate(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rcl", "capabilities", "list", "--json"])
    assert rcl_main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["registry_version"] == "0.1"
    assert {
        item["capability_id"] for item in payload["capabilities"]
    } == EXPECTED_INITIAL_CAPABILITIES

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rcl",
            "capabilities",
            "validate",
            "x.acme.stereo_person_tracking",
            "--json",
        ],
    )
    assert rcl_main() == 0
    extension = json.loads(capsys.readouterr().out)
    assert extension["kind"] == "extension"
    assert extension["owner"] == "acme"
