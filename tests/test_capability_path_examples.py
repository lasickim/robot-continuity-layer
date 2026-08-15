import json
from pathlib import Path

from rcl.capability_paths import validate_intent_capability_paths
from rcl.profile import validate_schema


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reference_intent_example_is_valid():
    intent = _read(_root() / "examples" / "capability-paths" / "pre-sit-intent.json")
    validate_intent_capability_paths(intent)
    synthetic = {
        "behaviors": [
            {
                "behavior_id": "safety.pre_sit_clearance_check",
                "parameters": {},
                "preservation": {"priority": "required", "mode": "semantic"},
                "intent": intent,
            }
        ]
    }
    validate_schema(synthetic, "behavior")


def test_reference_target_examples_are_valid():
    base = _root() / "examples" / "capability-paths"
    for name in (
        "target-direct.embodiment.json",
        "target-rear-attention.embodiment.json",
        "target-external.embodiment.json",
    ):
        validate_schema(_read(base / name), "embodiment")
