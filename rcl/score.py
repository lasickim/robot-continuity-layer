from __future__ import annotations

from typing import Any


PRIORITY_WEIGHTS = {
    "required": 4.0,
    "preferred": 2.0,
    "optional": 1.0,
}


def calculate_continuity_score(
    source_behaviors: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate the v0.2 Behavior Continuity Score."""
    by_id = {item["behavior_id"]: item for item in results}
    weighted_sum = 0.0
    total_weight = 0.0
    required_failures: list[str] = []
    safety_blocks: list[str] = []
    details: list[dict[str, Any]] = []

    for behavior in source_behaviors:
        behavior_id = behavior["behavior_id"]
        priority = behavior["preservation"]["priority"]
        weight = PRIORITY_WEIGHTS[priority]
        result = by_id.get(behavior_id)
        if result is None:
            similarity = 0.0
            status = "unsupported"
        else:
            similarity = float(result["similarity"])
            status = result["status"]

        weighted_sum += weight * similarity
        total_weight += weight
        if priority == "required" and status in {"unsupported", "blocked_for_safety"}:
            required_failures.append(behavior_id)
        if status == "blocked_for_safety":
            safety_blocks.append(behavior_id)

        details.append({
            "behavior_id": behavior_id,
            "priority": priority,
            "weight": weight,
            "status": status,
            "similarity": round(similarity, 6),
            "weighted_similarity": round(weight * similarity, 6),
        })

    score = 100.0 if total_weight == 0 else (weighted_sum / total_weight) * 100.0
    return {
        "method": "rcl.behavior.weighted_similarity.v0.2",
        "score": round(score, 2),
        "migration_success": len(required_failures) == 0,
        "required_failures": required_failures,
        "safety_blocks": safety_blocks,
        "details": details,
    }
