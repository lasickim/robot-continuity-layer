from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


MIGRATION_STATUSES = (
    "preserved",
    "approximated",
    "unsupported",
    "blocked_for_safety",
)


@dataclass(frozen=True)
class BehaviorMigrationResult:
    behavior_id: str
    status: str
    similarity: float
    reason: str
    mapped_parameters: dict[str, Any] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in MIGRATION_STATUSES:
            raise ValueError(f"Unsupported migration status: {self.status}")
        if not 0.0 <= self.similarity <= 1.0:
            raise ValueError("similarity must be between 0 and 1")
        if self.status in {"unsupported", "blocked_for_safety"} and self.similarity != 0.0:
            raise ValueError(f"{self.status} results must use similarity=0.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "behavior_id": self.behavior_id,
            "status": self.status,
            "similarity": round(self.similarity, 6),
            "reason": self.reason,
            "required_capabilities": list(self.required_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
            "mapped_parameters": self.mapped_parameters,
        }


class RCLAdapter(ABC):
    """Translate semantic RCL behavior into a target embodiment representation.

    v0.2 adapters generate a migration plan. They do not directly command hardware.
    Hardware execution belongs to a platform integration layer.
    """

    adapter_id: str
    adapter_version: str

    @abstractmethod
    def supports(self, target_embodiment: dict[str, Any]) -> bool:
        """Return whether this adapter can target the supplied embodiment."""

    def required_capabilities(self, behavior: dict[str, Any]) -> set[str]:
        declared = behavior.get("required_capabilities", [])
        return set(declared)

    def capability_match(
        self,
        behavior: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> tuple[set[str], set[str]]:
        required = self.required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        return required & available, required - available

    @abstractmethod
    def translate_behavior(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> BehaviorMigrationResult:
        """Translate one semantic behavior to the target embodiment."""
