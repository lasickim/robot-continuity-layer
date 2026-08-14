from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable

from .profile import validate_schema


REGISTRY_VERSION = "0.1"
REGISTRY_RESOURCE = "capability-registry-v0.1.json"

_SEGMENT = r"[a-z][a-z0-9_]*"
_OWNER = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_STANDARD_RE = re.compile(rf"^(?P<namespace>{_SEGMENT})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")
_EXTENSION_RE = re.compile(rf"^x\.(?P<owner>{_OWNER})\.(?P<path>{_SEGMENT}(?:\.{_SEGMENT})*)$")


class CapabilityValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CapabilityClassification:
    capability_id: str
    kind: str
    valid: bool
    registered: bool
    namespace: str | None = None
    owner: str | None = None
    message: str = ""
    definition: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "kind": self.kind,
            "valid": self.valid,
            "registered": self.registered,
            "namespace": self.namespace,
            "owner": self.owner,
            "message": self.message,
            "definition": self.definition,
        }


@lru_cache(maxsize=1)
def load_capability_registry() -> dict[str, Any]:
    resource = files("rcl").joinpath("data", REGISTRY_RESOURCE)
    registry = json.loads(resource.read_text(encoding="utf-8"))
    validate_schema(registry, "capability-registry")

    capabilities = registry["capabilities"]
    ids = [item["capability_id"] for item in capabilities]
    if len(ids) != len(set(ids)):
        raise CapabilityValidationError("Capability registry contains duplicate capability_id values")

    reserved = {item["namespace"] for item in registry["reserved_namespaces"]}
    for item in capabilities:
        capability_id = item["capability_id"]
        match = _STANDARD_RE.fullmatch(capability_id)
        if match is None:
            raise CapabilityValidationError(
                f"Registered capability has invalid standard ID: {capability_id}"
            )
        namespace = match.group("namespace")
        if namespace not in reserved:
            raise CapabilityValidationError(
                f"Registered capability uses an unreserved namespace: {capability_id}"
            )
        if item["namespace"] != namespace:
            raise CapabilityValidationError(
                f"Registry namespace mismatch for {capability_id}: {item['namespace']}"
            )

    return registry


def registered_capabilities() -> list[dict[str, Any]]:
    return [dict(item) for item in load_capability_registry()["capabilities"]]


def reserved_namespaces() -> set[str]:
    return {
        item["namespace"]
        for item in load_capability_registry()["reserved_namespaces"]
    }


def get_capability(capability_id: str) -> dict[str, Any] | None:
    for item in load_capability_registry()["capabilities"]:
        if item["capability_id"] == capability_id:
            return dict(item)
    return None


def classify_capability_id(capability_id: str) -> CapabilityClassification:
    if not isinstance(capability_id, str) or not capability_id:
        return CapabilityClassification(
            capability_id=str(capability_id),
            kind="invalid",
            valid=False,
            registered=False,
            message="Capability ID must be a non-empty string.",
        )

    definition = get_capability(capability_id)
    if definition is not None:
        return CapabilityClassification(
            capability_id=capability_id,
            kind="standard",
            valid=True,
            registered=True,
            namespace=definition["namespace"],
            message="Registered RCL standard capability.",
            definition=definition,
        )

    extension = _EXTENSION_RE.fullmatch(capability_id)
    if extension is not None:
        return CapabilityClassification(
            capability_id=capability_id,
            kind="extension",
            valid=True,
            registered=False,
            namespace="x",
            owner=extension.group("owner"),
            message="Valid experimental/vendor extension capability.",
        )

    standard = _STANDARD_RE.fullmatch(capability_id)
    if standard is not None:
        namespace = standard.group("namespace")
        if namespace in reserved_namespaces():
            return CapabilityClassification(
                capability_id=capability_id,
                kind="unknown_reserved",
                valid=False,
                registered=False,
                namespace=namespace,
                message=(
                    "Capability uses an RCL-reserved namespace but is not present "
                    f"in Capability Registry v{REGISTRY_VERSION}."
                ),
            )
        return CapabilityClassification(
            capability_id=capability_id,
            kind="unreserved",
            valid=False,
            registered=False,
            namespace=namespace,
            message=(
                "Unregistered top-level namespaces are not portable RCL capability IDs. "
                "Use x.<owner>.<semantic_name> for extensions."
            ),
        )

    return CapabilityClassification(
        capability_id=capability_id,
        kind="invalid",
        valid=False,
        registered=False,
        message=(
            "Malformed capability ID. Standard IDs use <namespace>.<semantic_path>; "
            "extensions use x.<owner>.<semantic_path>."
        ),
    )


def validate_capability_id(
    capability_id: str,
    *,
    allow_extensions: bool = True,
) -> CapabilityClassification:
    result = classify_capability_id(capability_id)
    if result.kind == "extension" and allow_extensions:
        return result
    if result.kind == "standard" and result.valid:
        return result
    if result.kind == "extension" and not allow_extensions:
        raise CapabilityValidationError(
            f"Extension capability is not allowed in this context: {capability_id}"
        )
    raise CapabilityValidationError(f"{capability_id}: {result.message}")


def validate_capability_set(
    capabilities: Iterable[str],
    *,
    allow_extensions: bool = True,
) -> list[CapabilityClassification]:
    values = list(capabilities)
    if len(values) != len(set(values)):
        raise CapabilityValidationError("Capability list contains duplicate IDs")
    return [
        validate_capability_id(item, allow_extensions=allow_extensions)
        for item in values
    ]
