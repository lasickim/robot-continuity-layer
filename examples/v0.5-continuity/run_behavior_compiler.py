from __future__ import annotations

import json
from pathlib import Path

from rcl.behavior_compiler import compile_behavior_preserving_plan
from rcl.compatibility_mapping import map_behavioral_compatibility
from rcl.continuity_score import score_behavioral_continuity

HERE = Path(__file__).resolve().parent


def _read(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main() -> int:
    profile = _read("robot-a.continuity-profile.json")
    constraints = _read("identity-constraints.example.json")
    target = _read("robot-b.capability-manifest.json")
    mapping = map_behavioral_compatibility(profile, constraints, target)
    score = score_behavioral_continuity(profile, constraints, mapping)
    plan = compile_behavior_preserving_plan(mapping, score)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
