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


def _validate_status(status: str, similarity: float | None = None) -> None:
    if status not in MIGRATION_STATUSES:
        raise ValueError(f"Unsupported migration status: {status}")
    if similarity is not None:
        if not 0.0 <= similarity <= 1.0:
            raise ValueError("similarity must be between 0 and 1")
        if status in {"unsupported", "blocked_for_safety"} and similarity != 0.0:
            raise ValueError(f"{status} results must use similarity=0.0")


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
        _validate_status(self.status, self.similarity)

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


@dataclass(frozen=True)
class IntentMigrationResult:
    goal_id: str
    status: str
    reason: str
    target_strategy: str | None = None
    required_capabilities: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_status(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "status": self.status,
            "reason": self.reason,
            "target_strategy": self.target_strategy,
            "required_capabilities": list(self.required_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
        }


@dataclass(frozen=True)
class ExpressionMigrationResult:
    expression_id: str
    status: str
    reason: str
    target_expression: str | None = None
    required_capabilities: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_status(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression_id": self.expression_id,
            "status": self.status,
            "reason": self.reason,
            "target_expression": self.target_expression,
            "required_capabilities": list(self.required_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
        }


class RCLAdapter(ABC):
    """Translate semantic RCL behavior into a target embodiment representation.

    Adapters generate migration plans; they do not directly command hardware.
    v0.4 adds optional intent and visible-expression translation alongside the
    existing behavior translation. Existing adapters remain valid because the
    new facet methods provide conservative defaults.
    """

    adapter_id: str
    adapter_version: str

    @abstractmethod
    def supports(self, target_embodiment: dict[str, Any]) -> bool:
        """Return whether this adapter can target the supplied embodiment."""

    def required_capabilities(self, behavior: dict[str, Any]) -> set[str]:
        declared = behavior.get("required_capabilities", [])
        return set(declared)

    def intent_required_capabilities(self, behavior: dict[str, Any]) -> set[str]:
        intent = behavior.get("intent") or {}
        return set(intent.get("required_capabilities", []))

    def expression_required_capabilities(self, behavior: dict[str, Any]) -> set[str]:
        expression = behavior.get("expression") or {}
        return set(expression.get("required_capabilities", []))

    def capability_match(
        self,
        behavior: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> tuple[set[str], set[str]]:
        required = self.required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        return required & available, required - available

    def translate_intent(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> IntentMigrationResult | None:
        intent = behavior.get("intent")
        if intent is None:
            return None

        required = self.intent_required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="unsupported",
                reason="Target lacks capabilities required to satisfy the declared intent.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )
        return IntentMigrationResult(
            goal_id=intent["goal_id"],
            status="preserved",
            reason="Target exposes the semantic capabilities required by the declared intent.",
            required_capabilities=tuple(sorted(required)),
        )

    def translate_expression(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> ExpressionMigrationResult | None:
        expression = behavior.get("expression")
        if expression is None:
            return None

        required = self.expression_required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        if missing:
            return ExpressionMigrationResult(
                expression_id=expression["expression_id"],
                status="unsupported",
                reason="Target cannot reproduce the declared visible expression with its available capabilities.",
                required_capabilities=tuple(sorted(required)),
                missing_capabilities=tuple(sorted(missing)),
            )
        return ExpressionMigrationResult(
            expression_id=expression["expression_id"],
            status="preserved",
            reason="Target can reproduce the declared visible expression.",
            target_expression=expression["expression_id"],
            required_capabilities=tuple(sorted(required)),
        )

    @abstractmethod
    def translate_behavior(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> BehaviorMigrationResult:
        """Translate one semantic behavior to the target embodiment."""
