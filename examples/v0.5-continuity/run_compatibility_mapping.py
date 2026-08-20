from __future__ import annotations

import json
from pathlib import Path

from rcl.compatibility_mapping import map_behavioral_compatibility


HERE = Path(__file__).resolve().parent


def _read(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main() -> int:
    report = map_behavioral_compatibility(
        _read("robot-a.continuity-profile.json"),
        _read("identity-constraints.example.json"),
        _read("robot-b.capability-manifest.json"),
        created_at="2026-08-20T10:00:00Z",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
