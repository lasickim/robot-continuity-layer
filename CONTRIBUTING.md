# Contributing to RCL

RCL is an experimental open specification. Contributions that challenge the model, expose ambiguity, or demonstrate failure cases are welcome alongside code changes.

## Before opening a pull request

1. Read [`README.md`](README.md), [`spec/rcl-spec-v0.2.md`](spec/rcl-spec-v0.2.md), and [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).
2. Keep continuity semantics separate from hardware-specific execution whenever possible.
3. Do not represent an approximation as exact preservation.
4. Do not allow a legacy behavior or continuity preference to override target safety constraints.
5. Add or update tests for behavior-changing code.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

## Good first contributions

Useful early contributions include:

- review or critique of the semantic behavior schema;
- new example behaviors and edge cases;
- new embodiment capability vocabulary;
- adapters for simulators, ROS 2 robots, or research platforms;
- migration reports that expose unsupported or approximated behavior;
- conformance and evaluation test ideas;
- documentation improvements.

## Proposing a semantic behavior

A behavior proposal should describe **meaning before implementation**.

Prefer:

```yaml
human_following:
  preferred_distance_m: 1.4
  speed_style: gentle
  stop_delay_ms: 350
```

Avoid making hardware commands canonical RCL semantics:

```yaml
left_motor_pwm: 34
right_motor_pwm: 31
```

Hardware-specific values belong in an embodiment adapter or target execution plan.

A useful proposal should answer:

- What observable behavior is being preserved?
- Which parameters are meaningfully portable?
- What target capabilities are required?
- How can the behavior degrade safely?
- How could preservation be measured?

## Migration result integrity

Adapters must classify behavior honestly:

- `preserved` — the semantic behavior can be reproduced within the declared tolerance;
- `approximated` — a meaningful substitute exists but differs from the source behavior;
- `unsupported` — the target lacks the capability needed to reproduce it;
- `blocked_for_safety` — reproduction would violate target safety constraints or policy.

A high Continuity Score must never hide failure of a required behavior.

## Pull requests

Keep pull requests focused. Explain:

- what changed;
- why it belongs in the continuity layer rather than a hardware-specific layer;
- how compatibility is affected;
- what tests or evaluation were performed.

Specification changes should include a concrete example whenever possible.

## Compatibility and versioning

RCL is pre-1.0. Schemas and semantics may change while the project learns from real robot integrations. Implementations should declare the RCL version they support rather than claiming generic compatibility.

## Safety

Do not submit examples or adapters that intentionally bypass robot safety systems. RCL continuity is subordinate to the physical and software safety constraints of the target robot.

## License

Unless explicitly stated otherwise, contributions submitted to this repository are provided under the repository's Apache License 2.0 terms.
