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
    for item in source_behavior["behaviors"]:
        # Validate the adapter's complete semantic requirement set, including
        # capabilities the adapter adds beyond those declared in the profile.
        validate_capability_set(adapter.required_capabilities(item))
        results.append(
            adapter.translate_behavior(
                item,
                source_embodiment,
                target_embodiment,
            ).to_dict()
        )

    score = calculate_continuity_score(source_behavior["behaviors"], results)

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
