from __future__ import annotations

from typing import Any

from .profile import RCLValidationError, validate_schema


CONTEXT_VERSION = "0.1"
DEFAULT_COMPARISON_FIELDS = (
    "task_id",
    "environment_id",
    "start_condition_id",
)
COMPARABLE_CONTEXT_FIELDS = {
    "task_id",
    "environment_id",
    "subject_ref",
    "operator_ref",
    "start_condition_id",
}
INFORMATIONAL_CONTEXT_FIELDS = (
    "subject_ref",
    "operator_ref",
    "software_ref",
    "adapter_ref",
    "sensor_config_ref",
    "notes",
)


def _comparison_fields(protocol: dict[str, Any]) -> tuple[str, ...]:
    fields = tuple(protocol.get("comparison_fields") or DEFAULT_COMPARISON_FIELDS)
    if len(fields) != len(set(fields)):
        raise RCLValidationError("Experiment protocol comparison_fields contains duplicates")
    unknown = [field for field in fields if field not in COMPARABLE_CONTEXT_FIELDS]
    if unknown:
        raise RCLValidationError(
            f"Experiment protocol contains unsupported comparison fields: {unknown}"
        )
    return fields


def compare_experiment_context(
    source_trials: dict[str, Any],
    target_trials: dict[str, Any],
) -> dict[str, Any]:
    """Compare declared experimental context before statistical scoring.

    The check is intentionally declarative. It verifies that both captures claim
    the same protocol and the same values for protocol-selected comparison
    fields. It cannot prove that two physical environments are truly identical.
    """

    source_experiment = source_trials.get("experiment")
    target_experiment = target_trials.get("experiment")
    if not isinstance(source_experiment, dict) or not isinstance(target_experiment, dict):
        raise RCLValidationError("Repeated-trial captures must include experiment metadata")

    source_protocol = source_experiment.get("protocol")
    target_protocol = target_experiment.get("protocol")
    source_context = source_experiment.get("context")
    target_context = target_experiment.get("context")
    if not isinstance(source_protocol, dict) or not isinstance(target_protocol, dict):
        raise RCLValidationError("Repeated-trial captures must include experiment.protocol")
    if not isinstance(source_context, dict) or not isinstance(target_context, dict):
        raise RCLValidationError("Repeated-trial captures must include experiment.context")

    validate_schema(source_protocol, "experiment-protocol")
    validate_schema(target_protocol, "experiment-protocol")

    source_fields = _comparison_fields(source_protocol)
    target_fields = _comparison_fields(target_protocol)
    mismatches: list[dict[str, Any]] = []

    def mismatch(field: str, source: Any, target: Any, reason: str) -> None:
        mismatches.append(
            {
                "field": field,
                "source": source,
                "target": target,
                "reason": reason,
            }
        )

    if source_protocol["protocol_id"] != target_protocol["protocol_id"]:
        mismatch(
            "protocol_id",
            source_protocol["protocol_id"],
            target_protocol["protocol_id"],
            "protocol_mismatch",
        )
    if source_protocol["protocol_version"] != target_protocol["protocol_version"]:
        mismatch(
            "protocol_version",
            source_protocol["protocol_version"],
            target_protocol["protocol_version"],
            "protocol_mismatch",
        )
    if source_fields != target_fields:
        mismatch(
            "comparison_fields",
            list(source_fields),
            list(target_fields),
            "protocol_mismatch",
        )

    fields = source_fields if source_fields == target_fields else tuple(
        dict.fromkeys(source_fields + target_fields)
    )
    for field in fields:
        source_present = field in source_context
        target_present = field in target_context
        source_value = source_context.get(field)
        target_value = target_context.get(field)
        if not source_present and not target_present:
            mismatch(field, None, None, "missing_both")
        elif not source_present:
            mismatch(field, None, target_value, "missing_source")
        elif not target_present:
            mismatch(field, source_value, None, "missing_target")
        elif source_value != target_value:
            mismatch(field, source_value, target_value, "value_mismatch")

    informational_differences: list[dict[str, Any]] = []
    for field in INFORMATIONAL_CONTEXT_FIELDS:
        if field in fields:
            continue
        source_value = source_context.get(field)
        target_value = target_context.get(field)
        if source_value != target_value:
            informational_differences.append(
                {
                    "field": field,
                    "source": source_value,
                    "target": target_value,
                }
            )

    return {
        "context_version": CONTEXT_VERSION,
        "compatible": not mismatches,
        "source_protocol": {
            "protocol_id": source_protocol["protocol_id"],
            "protocol_version": source_protocol["protocol_version"],
        },
        "target_protocol": {
            "protocol_id": target_protocol["protocol_id"],
            "protocol_version": target_protocol["protocol_version"],
        },
        "comparison_fields": list(fields),
        "mismatches": mismatches,
        "informational_differences": informational_differences,
    }
