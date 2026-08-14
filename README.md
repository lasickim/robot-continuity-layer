# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.3-dev**

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

## What works today — v0.3-dev

The reference implementation can:

- validate and package portable `.rcl` profiles;
- verify profile integrity with SHA-256 manifests;
- describe source and target embodiments;
- perform semantic capability matching;
- validate capability IDs against Capability Registry v0.1 while allowing isolated `x.<owner>.*` extensions;
- classify migration results as `preserved`, `approximated`, `unsupported`, or `blocked_for_safety`;
- generate a machine-readable migration report;
- calculate a transparent Behavior Continuity Score;
- reject overall migration success when a required behavior cannot be safely preserved;
- translate mobile-base continuity behavior into a ROS 2 execution plan through the experimental `rcl_ros2` integration;
- run an executable adapter conformance suite with machine-readable results.

Reference migration result:

```text
Continuity Score: 88.33%
Migration Success: YES
- navigation.follow_person: preserved (similarity=1.00)
- navigation.pre_turn_observation: approximated (similarity=0.65)
```

## Capability Registry v0.1

RCL now publishes a small formal vocabulary for semantic robot capabilities.

Initial standard IDs are:

```text
navigation.planar_velocity
perception.person_tracking
perception.forward_range
perception.directional_attention
```

Standard-looking names inside an RCL-reserved namespace must exist in the registry. For example:

```text
perception.person_tracking   VALID
perception.telepathy         INVALID — reserved but unregistered
```

Independent implementations can experiment without waiting for a registry change by using the extension namespace:

```text
x.<owner>.<semantic_path>
```

Example:

```text
x.acme.stereo_person_tracking
```

The capability describes **what an embodiment can semantically provide**, not how it is implemented. ROS topics, vendor SDK calls, motor values, and controller details remain adapter concerns.

CLI:

```bash
rcl capabilities list
rcl capabilities show perception.person_tracking
rcl capabilities validate perception.person_tracking
rcl capabilities validate x.acme.stereo_person_tracking
```

See [`docs/CAPABILITY_REGISTRY.md`](docs/CAPABILITY_REGISTRY.md) and the machine-readable [`spec/capability-registry-v0.1.json`](spec/capability-registry-v0.1.json).

## ROS 2 reference adapter

The v0.3-dev branch includes the first middleware integration while keeping ROS-specific details outside the portable profile:

```text
portable .rcl profile
        ↓
ROS2MobileBaseAdapter
        ↓
ROS-facing execution plan
        ↓
TwistPublisher / controller
        ↓
mobile base
```

The first reference target is a ROS 2 Lyrical mobile base using `geometry_msgs/msg/Twist` for planar velocity. A semantic style such as `gentle` is mapped relative to the **target robot's declared limits**, rather than copying source motor percentages.

The ROS runtime dependency is lazy: importing and unit-testing the adapter does not require ROS 2 to be installed.

See [`docs/ROS2_REFERENCE_ADAPTER.md`](docs/ROS2_REFERENCE_ADAPTER.md).

## Adapter conformance

RCL v0.3-dev also includes the first executable compatibility check. A zero-argument Python adapter can run against the published mobile-base fixture with:

```bash
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
```

Expected reference output:

```text
RCL Adapter Conformance
Profile      PASS
Adapter      PASS
Migration    PASS
Safety       PASS
Reporting    PASS

Result: RCL Migration Compatible (experimental v0.3)
```

The initial suite ID is:

```text
rcl.adapter.mobile_base.v0.3
```

The suite deliberately removes capabilities in negative cases. An adapter that silently reports missing required capabilities as `preserved` fails conformance. The full migration path also rejects unknown capability names inside RCL-reserved namespaces.

For CI or registry tooling:

```bash
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter --json
```

This is an **experimental protocol conformance result**, not physical robot safety certification or identity proof. See [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

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
| **RCL Migration Compatible** | Can translate semantic behavior to another embodiment, expose degradation, and produce an explicit migration report. v0.3 adds the first executable mobile-base suite. |
| **RCL Continuity Ready** | Future real-robot level with live capture, restore, and reproducible observed-behavior evaluation. |

These are experimental v0.x compatibility concepts, not a formal certification program. See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

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

rcl capabilities list
rcl validate examples/mobile-base
rcl pack examples/mobile-base /tmp/robot-a.rcl
rcl inspect /tmp/robot-a.rcl

rcl migrate \
  /tmp/robot-a.rcl \
  examples/targets/demo-rover-b.embodiment.json \
  --output /tmp/migration-report.json

rcl report /tmp/migration-report.json
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
pytest -q
```

Minimal ROS 2 semantic translation:

```python
from rcl_ros2 import ROS2MobileBaseAdapter

adapter = ROS2MobileBaseAdapter(cmd_vel_topic="/cmd_vel")
result = adapter.translate_behavior(behavior, source_embodiment, target_embodiment)
print(result.mapped_parameters)
```

## Continuity Score v0.2

The current score intentionally stays simple and auditable:

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
- proposing capability registry additions with concrete interoperability use cases;
- documenting useful `x.<owner>.*` extension capabilities;
- implementing adapters for real or simulated robots;
- running the conformance suite against an independently implemented adapter;
- designing migration evaluation scenarios;
- finding ambiguous or unsafe parts of the draft specification.

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`ROADMAP.md`](ROADMAP.md), and the open GitHub issues.

## Repository layout

```text
robot-continuity-layer/
├── README.md
├── CONTRIBUTING.md
├── ROADMAP.md
├── docs/
│   ├── CAPABILITY_REGISTRY.md
│   ├── COMPATIBILITY.md
│   ├── CONFORMANCE.md
│   └── ROS2_REFERENCE_ADAPTER.md
├── spec/
│   ├── capability-registry-v0.1.json
│   └── schemas/
│       ├── capability-registry.schema.json
│       └── conformance-report.schema.json
├── examples/
├── rcl/
│   ├── adapter.py
│   ├── capabilities.py
│   ├── conformance.py
│   ├── conformance_cli.py
│   ├── data/
│   │   └── capability-registry-v0.1.json
│   ├── migration.py
│   ├── profile.py
│   └── score.py
├── rcl_ros2/
│   ├── adapter.py
│   └── runtime.py
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective identity, or emotional authenticity. It describes portable robot continuity data and measures how well declared behaviors survive migration.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
