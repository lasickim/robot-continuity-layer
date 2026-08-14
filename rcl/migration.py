from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .adapter import RCLAdapter
from .capabilities import validate_capability_set
from .profile import RCLProfile, validate_schema
from .score import calculate_continuity_score


def migrate_profile(
    profile: RCLProfile,
    target_embodiment: dict[str, Any],
    adapter: RCLAdapter,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_schema(target_embodiment, "embodiment")

    source_identity = profile.load("identity.json")
    source_behavior = profile.load("behavior.json")
    source_embodiment = profile.load("embodiment.json")
    manifest = profile.load("manifest.json") if (profile.root / "manifest.json").exists() else None

    validate_capability_set(source_embodiment.get("capabilities", []))
    validate_capability_set(target_embodiment.get("capabilities", []))

    if not adapter.supports(target_embodiment):
        raise ValueError(
            f"Adapter {adapter.adapter_id} does not support target embodiment "
            f"{target_embodiment.get('embodiment_id', '<unknown>')}"
        )

    results: list[dict[str, Any]] = []
    intent_required_failures: list[str] = []
    has_intent = False

    for item in source_behavior["behaviors"]:
        validate_capability_set(adapter.required_capabilities(item))
        validate_capability_set(adapter.intent_required_capabilities(item))
        validate_capability_set(adapter.expression_required_capabilities(item))

        behavior_result = adapter.translate_behavior(
            item,
            source_embodiment,
            target_embodiment,
        ).to_dict()

        intent_result = adapter.translate_intent(
            item,
            source_embodiment,
            target_embodiment,
        )
        if intent_result is not None:
            has_intent = True
            behavior_result["intent_result"] = intent_result.to_dict()
            intent = item["intent"]
            if (
                intent["criticality"] == "required"
                and intent_result.status in {"unsupported", "blocked_for_safety"}
            ):
                intent_required_failures.append(f"intent:{item['behavior_id']}")

        expression_result = adapter.translate_expression(
            item,
            source_embodiment,
            target_embodiment,
        )
        if expression_result is not None:
            behavior_result["expression_result"] = expression_result.to_dict()

        expression_timing_result = adapter.translate_expression_timing(
            item,
            source_embodiment,
            target_embodiment,
        )
        if expression_timing_result is not None:
            behavior_result["expression_timing_result"] = expression_timing_result.to_dict()

        results.append(behavior_result)

    score = calculate_continuity_score(source_behavior["behaviors"], results)
    if has_intent:
        score["intent_required_failures"] = sorted(intent_required_failures)
    if intent_required_failures:
        score["migration_success"] = False
        score["required_failures"] = sorted(
            set(score["required_failures"]) | set(intent_required_failures)
        )

    report = {
        "rcl_version": "0.2",
        "report_version": "0.2",
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "robot_id": source_identity["robot_id"],
            "profile_id": manifest["profile_id"] if manifest else None,
            "embodiment_id": source_embodiment["embodiment_id"],
        },
        "target": {
            "embodiment_id": target_embodiment["embodiment_id"],
            "vendor": target_embodiment.get("vendor"),
            "model": target_embodiment.get("model"),
        },
        "adapter": {
            "adapter_id": adapter.adapter_id,
            "adapter_version": adapter.adapter_version,
        },
        "behavior_results": results,
        "continuity": score,
    }
    validate_schema(report, "migration-report")
    return report
