from __future__ import annotations

import copy
from typing import Any

from .capabilities import validate_capability_set
from .profile import RCLValidationError


CAPABILITY_PATHS_VERSION = "0.1"
LEGACY_CAPABILITY_PATH_ID = "legacy.required_capabilities"


def _path_capabilities(path: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("all_of", "any_of", "one_of"):
        values.extend(path.get(key, []))
    return values


def validate_intent_capability_paths(intent: dict[str, Any]) -> None:
    """Validate legacy required capabilities or v0.1 alternative capability paths."""

    has_legacy = "required_capabilities" in intent
    has_paths = "capability_paths" in intent
    if has_legacy == has_paths:
        raise RCLValidationError(
            "Intent must declare exactly one of required_capabilities or capability_paths"
        )

    if has_legacy:
        validate_capability_set(intent["required_capabilities"])
        if not intent["required_capabilities"]:
            raise RCLValidationError("Intent required_capabilities must not be empty")
        return

    paths = intent["capability_paths"]
    if not isinstance(paths, list) or not paths:
        raise RCLValidationError("Intent capability_paths must be a non-empty list")

    seen_path_ids: set[str] = set()
    for path in paths:
        path_id = path["path_id"]
        if path_id in seen_path_ids:
            raise RCLValidationError(f"Duplicate intent capability path_id: {path_id}")
        seen_path_ids.add(path_id)

        clauses = [key for key in ("all_of", "any_of", "one_of") if key in path]
        if not clauses:
            raise RCLValidationError(f"{path_id}: capability path requires at least one clause")

        all_values: list[str] = []
        for key in clauses:
            values = path[key]
            if not isinstance(values, list) or not values:
                raise RCLValidationError(f"{path_id}.{key} must be a non-empty list")
            validate_capability_set(values)
            all_values.extend(values)

        if len(all_values) != len(set(all_values)):
            raise RCLValidationError(
                f"{path_id}: the same capability must not appear in multiple clauses"
            )


def normalized_intent_capability_paths(intent: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit capability paths, adapting legacy flat requirements to one all_of path."""

    validate_intent_capability_paths(intent)
    if "capability_paths" in intent:
        return copy.deepcopy(intent["capability_paths"])
    return [
        {
            "path_id": LEGACY_CAPABILITY_PATH_ID,
            "all_of": list(intent["required_capabilities"]),
        }
    ]


def declared_intent_capabilities(intent: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()
    for path in normalized_intent_capability_paths(intent):
        capabilities.update(_path_capabilities(path))
    return capabilities


def _evaluate_clause(
    clause: str,
    options: list[str],
    available: set[str],
) -> dict[str, Any]:
    matched = sorted(set(options) & available)
    if clause == "all_of":
        missing = sorted(set(options) - available)
        satisfied = not missing
        selected = sorted(options) if satisfied else []
    elif clause == "any_of":
        missing = [] if matched else sorted(options)
        satisfied = bool(matched)
        selected = matched[:1]
    else:  # one_of means exactly one capability is selected, not exactly one is available.
        missing = [] if matched else sorted(options)
        satisfied = bool(matched)
        selected = matched[:1]

    return {
        "clause": clause,
        "options": list(options),
        "matched": matched,
        "missing": missing,
        "selected": selected,
        "satisfied": satisfied,
    }


def evaluate_intent_capability_paths(
    intent: dict[str, Any],
    available_capabilities: set[str] | list[str] | tuple[str, ...],
) -> list[dict[str, Any]]:
    """Evaluate every declared path without ranking one technology as universally superior."""

    paths = normalized_intent_capability_paths(intent)
    available = set(available_capabilities)
    validate_capability_set(available)

    results: list[dict[str, Any]] = []
    for path in paths:
        clause_results = [
            _evaluate_clause(key, path[key], available)
            for key in ("all_of", "any_of", "one_of")
            if key in path
        ]
        satisfied = all(item["satisfied"] for item in clause_results)
        selected: set[str] = set()
        for item in clause_results:
            selected.update(item["selected"])
        results.append(
            {
                "path_id": path["path_id"],
                "satisfied": satisfied,
                "selected_capabilities": sorted(selected) if satisfied else [],
                "clauses": clause_results,
                "reason": (
                    "all_capability_clauses_satisfied"
                    if satisfied
                    else "one_or_more_capability_clauses_unsatisfied"
                ),
            }
        )
    return results


def select_satisfied_capability_path(
    intent: dict[str, Any],
    available_capabilities: set[str] | list[str] | tuple[str, ...],
    *,
    preferred_path_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any] | None:
    """Select one satisfied path deterministically.

    Adapters may supply embodiment-specific preferred path IDs. Otherwise the
    declaration order is the deterministic fallback and does not imply a global
    quality ranking between sensing or actuation technologies.
    """

    results = evaluate_intent_capability_paths(intent, available_capabilities)
    by_id = {item["path_id"]: item for item in results}
    if preferred_path_ids:
        for path_id in preferred_path_ids:
            item = by_id.get(path_id)
            if item is not None and item["satisfied"]:
                return copy.deepcopy(item)
    for item in results:
        if item["satisfied"]:
            return copy.deepcopy(item)
    return None
