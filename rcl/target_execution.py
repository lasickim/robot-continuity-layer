from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from .profile import RCLValidationError, validate_schema


TARGET_EXECUTION_VERSION = "0.1"


class TargetExecutionAdapter(Protocol):
    """Vendor-neutral adapter boundary consumed by RCL execution dispatch."""

    def execute(self, instruction: dict[str, Any]) -> dict[str, Any]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_adapter_result(result: dict[str, Any], constraint_id: str) -> None:
    if not isinstance(result, dict):
        raise RCLValidationError(
            f"adapter result for {constraint_id} must be an object"
        )
    if not isinstance(result.get("success"), bool):
        raise RCLValidationError(
            f"adapter result for {constraint_id} requires boolean success"
        )
    evidence_refs = result.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or any(
        not isinstance(ref, str) or not ref for ref in evidence_refs
    ):
        raise RCLValidationError(
            f"adapter result for {constraint_id} evidence_refs must be non-empty strings"
        )
    message = result.get("message")
    if message is not None and (not isinstance(message, str) or not message):
        raise RCLValidationError(
            f"adapter result for {constraint_id} message must be a non-empty string"
        )


def build_execution_bundle(
    compiler_plan: dict[str, Any],
    *,
    adapter_id: str,
    execution_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a fail-closed adapter bundle from a compiler plan.

    Only a globally READY compiler plan becomes dispatchable. REVIEW_REQUIRED or
    BLOCKED plans preserve their instructions for inspection but expose no
    executable instruction list.
    """

    validate_schema(compiler_plan, "behavior-compiler-plan")
    if not adapter_id:
        raise RCLValidationError("adapter_id must not be empty")
    if not execution_id:
        raise RCLValidationError("execution_id must not be empty")

    plan_status = compiler_plan["summary"]["plan_status"]
    dispatch_allowed = plan_status == "READY"
    executable = (
        [
            item
            for item in compiler_plan["instructions"]
            if item["execution_status"] == "READY"
        ]
        if dispatch_allowed
        else []
    )

    blocked_reasons = [
        {
            "constraint_id": item["constraint_id"],
            "execution_status": item["execution_status"],
            "reason": item["reason"],
        }
        for item in compiler_plan["instructions"]
        if item["execution_status"] != "READY"
    ]

    bundle = {
        "target_execution_version": TARGET_EXECUTION_VERSION,
        "created_at": created_at or _now(),
        "execution_id": execution_id,
        "adapter_id": adapter_id,
        "source_robot_id": compiler_plan["source_robot_id"],
        "source_profile_id": compiler_plan["source_profile_id"],
        "constraint_set_id": compiler_plan["constraint_set_id"],
        "target_robot_id": compiler_plan["target_robot_id"],
        "target_embodiment_id": compiler_plan["target_embodiment_id"],
        "compiler_plan_status": plan_status,
        "dispatch_allowed": dispatch_allowed,
        "instructions": executable,
        "blocked_reasons": blocked_reasons,
    }
    validate_schema(bundle, "target-execution-bundle")
    return bundle


def execute_target_bundle(
    bundle: dict[str, Any],
    adapter: TargetExecutionAdapter,
    *,
    completed_at: str | None = None,
) -> dict[str, Any]:
    """Dispatch a validated READY bundle through an injected target adapter."""

    validate_schema(bundle, "target-execution-bundle")
    if not bundle["dispatch_allowed"]:
        raise RCLValidationError(
            f"target execution blocked by compiler plan status: {bundle['compiler_plan_status']}"
        )

    results: list[dict[str, Any]] = []
    all_success = True
    for instruction in bundle["instructions"]:
        raw = adapter.execute(instruction)
        _validate_adapter_result(raw, instruction["constraint_id"])
        success = bool(raw["success"])
        all_success = all_success and success
        item = {
            "constraint_id": instruction["constraint_id"],
            "behavior_id": instruction["behavior_id"],
            "dimension": instruction["dimension"],
            "success": success,
            "evidence_refs": list(raw.get("evidence_refs", [])),
        }
        if "message" in raw:
            item["message"] = raw["message"]
        results.append(item)

    report = {
        "target_execution_report_version": TARGET_EXECUTION_VERSION,
        "completed_at": completed_at or _now(),
        "execution_id": bundle["execution_id"],
        "adapter_id": bundle["adapter_id"],
        "target_robot_id": bundle["target_robot_id"],
        "target_embodiment_id": bundle["target_embodiment_id"],
        "result": "SUCCESS" if all_success else "FAILED",
        "instruction_results": results,
        "summary": {
            "attempted": len(results),
            "succeeded": sum(1 for item in results if item["success"]),
            "failed": sum(1 for item in results if not item["success"]),
        },
    }
    validate_schema(report, "target-execution-report")
    return report
