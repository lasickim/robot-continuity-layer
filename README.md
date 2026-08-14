# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.2**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an open specification and reference implementation for preserving a robot's **experience, preferences, semantic behavior, and skill history independently from its current hardware body**.

The core question is simple:

> When Robot A is replaced by Robot B, what should survive besides files and configuration?

RCL represents continuity semantically, then lets an embodiment adapter translate that intent to a different body.

```text
Robot A
  │
  │ experience + behavior
  ▼
robot-a.rcl
  │
  ▼
RCL Embodiment Adapter
  │
  ▼
Robot B
  │
  ▼
Migration Report + Continuity Score
```

## Why RCL exists

Raw joint angles, motor percentages, and vendor-specific settings do not transfer cleanly between different robots. RCL instead describes observable intent and style such as:

```yaml
handover:
  approach_style: gentle
  preferred_distance_m: 0.55
  wait_for_grasp: true
  release_style: gentle
```

A target adapter decides how its own hardware can reproduce that behavior and must explicitly report any degradation.

## What works today — v0.2

The current reference implementation can:

- validate and package portable `.rcl` profiles;
- verify profile integrity with SHA-256 manifests;
- describe source and target embodiments;
- perform semantic capability matching;
- classify migration results as `preserved`, `approximated`, `unsupported`, or `blocked_for_safety`;
- generate a machine-readable migration report;
- calculate a transparent Behavior Continuity Score;
- reject overall migration success when a required behavior cannot be safely preserved.

Reference result:

```text
Continuity Score: 88.33%
Migration Success: YES
- navigation.follow_person: preserved (similarity=1.00)
- navigation.pre_turn_observation: approximated (similarity=0.65)
```

## Core principles

1. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
2. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
3. **User-owned and portable** — continuity should export without requiring a vendor cloud.
4. **Graceful degradation** — unsupported behavior must be reported, never silently claimed as preserved.
5. **Observable continuity** — migration quality should be measurable and inspectable.
6. **Safety outranks continuity** — a legacy behavior never overrides target safety constraints.
7. **Scores do not define identity** — the Continuity Score measures declared behavior preservation only.

## Experimental compatibility levels

RCL is beginning to define interoperability levels:

| Level | Meaning |
|---|---|
| **RCL Profile Compatible** | Can safely read, validate, preserve, and write the portable profile format. |
| **RCL Migration Compatible** | Can translate semantic behavior to another embodiment and produce an explicit migration report. |
| **RCL Continuity Ready** | Future real-robot level with live capture, restore, reproducible evaluation, and conformance testing. |

These are **draft compatibility concepts, not a certification program yet**. See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

## `.rcl` package format

An `.rcl` file is currently a ZIP container:

```text
robot-a.rcl
├── manifest.json
├── identity.json
├── preferences.json
├── behavior.json
├── skills.json
└── embodiment.json
```

The manifest contains SHA-256 hashes for every payload file.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

rcl validate examples/mobile-base
rcl pack examples/mobile-base /tmp/robot-a.rcl
rcl inspect /tmp/robot-a.rcl

rcl migrate \
  /tmp/robot-a.rcl \
  examples/targets/demo-rover-b.embodiment.json \
  --output /tmp/migration-report.json

rcl report /tmp/migration-report.json
pytest -q
```

## Continuity Score v0.2

The v0.2 score intentionally stays simple and auditable:

```text
required  = weight 4
preferred = weight 2
optional  = weight 1

score = 100 × Σ(weight × similarity) / Σ(weight)
```

A required behavior that is unsupported or blocked for safety makes `migration_success=false` regardless of the numerical score.

## Who should experiment with RCL?

RCL is currently most useful for:

- robotics developers working with multiple embodiments;
- ROS 2 and robot middleware developers;
- research labs studying behavior transfer or lifelong robotics;
- robot manufacturers and system integrators exploring hardware replacement or fleet migration;
- developers interested in long-lived personal robots and user-owned robot history.

The project is early enough that **design feedback is as valuable as code**.

## Contributing

Good first contributions include:

- reviewing the semantic behavior model;
- proposing additional embodiment capabilities;
- implementing adapters for real or simulated robots;
- designing migration evaluation scenarios;
- finding ambiguous or unsafe parts of the draft specification;
- helping build the ROS 2 reference adapter and future conformance suite.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [`ROADMAP.md`](ROADMAP.md).

## Repository layout

```text
robot-continuity-layer/
├── README.md
├── CONTRIBUTING.md
├── ROADMAP.md
├── docs/
│   └── COMPATIBILITY.md
├── spec/
│   ├── rcl-spec-v0.1.md
│   ├── rcl-spec-v0.2.md
│   └── schemas/
├── examples/
├── rcl/
│   ├── adapter.py
│   ├── migration.py
│   ├── profile.py
│   ├── score.py
│   └── schemas/
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective identity, or emotional authenticity. It describes portable robot continuity data and measures how well declared behaviors survive migration.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
