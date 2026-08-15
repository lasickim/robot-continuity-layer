from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .capability_paths import (
    LEGACY_CAPABILITY_PATH_ID,
    declared_intent_capabilities,
    evaluate_intent_capability_paths,
    select_satisfied_capability_path,
)


MIGRATION_STATUSES = (
    "preserved",
    "approximated",
    "unsupported",
    "blocked_for_safety",
)

TIMING_MIGRATION_STATUSES = (
    "naturalized",
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


def _validate_timing_status(status: str) -> None:
    if status not in TIMING_MIGRATION_STATUSES:
        raise ValueError(f"Unsupported expression timing migration status: {status}")


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
    selected_capability_path_id: str | None = None
    capability_path_results: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _validate_status(self.status)
        if not self.capability_path_results and self.required_capabilities:
            required = sorted(set(self.required_capabilities))
            missing = sorted(set(self.missing_capabilities))
            matched = sorted(set(required) - set(missing))
            capability_satisfied = not missing
            selected = required if capability_satisfied else []
            result = {
                "path_id": LEGACY_CAPABILITY_PATH_ID,
                "satisfied": capability_satisfied,
                "selected_capabilities": selected,
                "clauses": [
                    {
                        "clause": "all_of",
                        "options": required,
                        "matched": matched,
                        "missing": missing,
                        "selected": selected,
                        "satisfied": capability_satisfied,
                    }
                ],
                "reason": (
                    "all_capability_clauses_satisfied"
                    if capability_satisfied
                    else "one_or_more_capability_clauses_unsatisfied"
                ),
            }
            object.__setattr__(self, "capability_path_results", (result,))
            if self.selected_capability_path_id is None and capability_satisfied:
                object.__setattr__(self, "selected_capability_path_id", LEGACY_CAPABILITY_PATH_ID)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "status": self.status,
            "reason": self.reason,
            "target_strategy": self.target_strategy,
            "required_capabilities": list(self.required_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
            "selected_capability_path_id": self.selected_capability_path_id,
            "capability_path_results": [dict(item) for item in self.capability_path_results],
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


@dataclass(frozen=True)
class ExpressionTimingMigrationResult:
    expression_id: str
    status: str
    reason: str
    timing_policy: str
    semantic_style: dict[str, Any]
    realized_timing: dict[str, Any] | None = None
    source_artifacts: tuple[dict[str, str], ...] = ()

    def __post_init__(self) -> None:
        _validate_timing_status(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression_id": self.expression_id,
            "status": self.status,
            "reason": self.reason,
            "timing_policy": self.timing_policy,
            "semantic_style": self.semantic_style,
            "realized_timing": self.realized_timing,
            "source_artifacts": [dict(item) for item in self.source_artifacts],
        }


class RCLAdapter(ABC):
    """Translate semantic RCL behavior into a target embodiment representation.

    Adapters generate migration plans; they do not directly command hardware.
    v0.4 adds optional intent, visible-expression, expressive-timing, and
    alternative capability-path translation alongside behavior translation.
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
        """Return the capability universe referenced by the Intent.

        For legacy flat requirements this is the historical all-required set.
        For alternative paths this is the union used for vocabulary validation;
        callers must use capability-path evaluation rather than treating the
        union as one all-required requirement.
        """

        intent = behavior.get("intent")
        if intent is None:
            return set()
        return declared_intent_capabilities(intent)

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

    def preferred_intent_capability_paths(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> tuple[str, ...]:
        """Optional embodiment-specific path preference without global ranking semantics."""

        return ()

    def translate_intent(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> IntentMigrationResult | None:
        intent = behavior.get("intent")
        if intent is None:
            return None

        available = set(target_embodiment.get("capabilities", []))
        path_results = evaluate_intent_capability_paths(intent, available)
        selected = select_satisfied_capability_path(
            intent,
            available,
            preferred_path_ids=list(
                self.preferred_intent_capability_paths(
                    behavior,
                    source_embodiment,
                    target_embodiment,
                )
            ),
        )
        if selected is None:
            declared = declared_intent_capabilities(intent)
            legacy_missing: tuple[str, ...] = ()
            if len(path_results) == 1 and path_results[0]["path_id"] == LEGACY_CAPABILITY_PATH_ID:
                clause = path_results[0]["clauses"][0]
                legacy_missing = tuple(clause["missing"])
            return IntentMigrationResult(
                goal_id=intent["goal_id"],
                status="unsupported",
                reason="Target satisfies none of the declared semantic capability paths for this intent.",
                required_capabilities=tuple(sorted(declared)),
                missing_capabilities=legacy_missing,
                selected_capability_path_id=None,
                capability_path_results=tuple(path_results),
            )

        return IntentMigrationResult(
            goal_id=intent["goal_id"],
            status="preserved",
            reason="Target satisfies a declared semantic capability path for this intent.",
            required_capabilities=tuple(selected["selected_capabilities"]),
            missing_capabilities=(),
            selected_capability_path_id=selected["path_id"],
            capability_path_results=tuple(path_results),
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

    def translate_expression_timing(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> ExpressionTimingMigrationResult | None:
        expression = behavior.get("expression")
        style = (expression or {}).get("temporal_style")
        if expression is None or style is None:
            return None

        required = self.expression_required_capabilities(behavior)
        available = set(target_embodiment.get("capabilities", []))
        missing = required - available
        semantic_style = {
            "tempo": style["tempo"],
            "dwell": style["dwell"],
            "transition": style["transition"],
            "legacy_significance": style["legacy_significance"],
        }
        if missing:
            return ExpressionTimingMigrationResult(
                expression_id=expression["expression_id"],
                status="unsupported",
                reason="Target cannot realize timing for an expression it cannot reproduce.",
                timing_policy=style["timing_policy"],
                semantic_style=semantic_style,
                source_artifacts=tuple(style.get("source_artifacts", [])),
            )

        status = "naturalized" if style["timing_policy"] == "naturalize" else "preserved"
        reason = (
            "Adapter accepts the portable temporal style; concrete timing remains target-defined."
        )
        return ExpressionTimingMigrationResult(
            expression_id=expression["expression_id"],
            status=status,
            reason=reason,
            timing_policy=style["timing_policy"],
            semantic_style=semantic_style,
            source_artifacts=tuple(style.get("source_artifacts", [])),
        )

    @abstractmethod
    def translate_behavior(
        self,
        behavior: dict[str, Any],
        source_embodiment: dict[str, Any],
        target_embodiment: dict[str, Any],
    ) -> BehaviorMigrationResult:
        """Translate one semantic behavior to the target embodiment."""
