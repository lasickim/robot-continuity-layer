# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.3-dev**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an open specification and reference implementation for preserving a robot's **experience, preferences, semantic behavior, and skill history independently from its current hardware body**.

The core question is simple:

> When Robot A is replaced by Robot B, what should survive besides files and configuration?

RCL now separates three different questions:

```text
What should survive?
        ↓
Portable semantic profile (.rcl)
        ↓
Can Robot B represent it?
        ↓
Migration Report + Declared Continuity Score
        ↓
Did Robot B actually behave close enough?
        ↓
Observed Continuity Evaluation
```

## Why RCL exists

Raw joint angles, motor percentages, topic names, and vendor-specific settings do not transfer cleanly between different robots. RCL instead describes observable intent and style:

```yaml
handover:
  approach_style: gentle
  preferred_distance_m: 0.55
  wait_for_grasp: true
  release_style: gentle
```

An embodiment adapter decides how its own hardware can reproduce that behavior and must explicitly report degradation.

## What works today — v0.3-dev

The reference implementation can:

- validate and package portable `.rcl` profiles;
- verify profile integrity with SHA-256 manifests;
- describe source and target embodiments;
- perform semantic capability matching;
- validate capability IDs against Capability Registry v0.1 while allowing isolated `x.<owner>.*` extensions;
- classify migration results as `preserved`, `approximated`, `unsupported`, or `blocked_for_safety`;
- generate machine-readable migration reports;
- calculate the declared Behavior Continuity Score;
- reject migration success when a required behavior cannot be safely preserved;
- translate mobile-base continuity behavior into a ROS 2 execution plan through `rcl_ros2`;
- run an executable adapter conformance suite;
- declare numeric behavior tolerances without duplicating semantic target values;
- ingest target-robot numeric observations;
- calculate an experimental Observed Continuity Score.

Reference declared migration:

```text
Continuity Score: 88.33%
Migration Success: YES
- navigation.follow_person: preserved (similarity=1.00)
- navigation.pre_turn_observation: approximated (similarity=0.65)
```

Reference observed evaluation:

```text
Declared target distance : 1.40 m
Observed Robot B distance: 1.37 m
Tolerance                : ±0.10 m

Declared stop delay      : 350 ms
Observed Robot B delay   : 372 ms
Tolerance                : ±80 ms

Observed Continuity Score: 100.00%
Evaluation Success       : YES
Status                   : within_tolerance
```

## Capability Registry v0.1

RCL publishes a small formal vocabulary for semantic robot capabilities.

Initial standard IDs:

```text
navigation.planar_velocity
perception.person_tracking
perception.forward_range
perception.directional_attention
```

Standard-looking names inside an RCL-reserved namespace must exist in the registry:

```text
perception.person_tracking   VALID
perception.telepathy         INVALID — reserved but unregistered
```

Independent implementations can experiment without waiting for a registry change:

```text
x.<owner>.<semantic_path>
```

Example:

```text
x.acme.stereo_person_tracking
```

Capabilities describe **what an embodiment can semantically provide**, not how it is implemented. ROS topics, vendor SDK calls, motor values, and controller details remain adapter concerns.

```bash
rcl capabilities list
rcl capabilities show perception.person_tracking
rcl capabilities validate x.acme.stereo_person_tracking
```

See [`docs/CAPABILITY_REGISTRY.md`](docs/CAPABILITY_REGISTRY.md).

## Behavior tolerance and observed evaluation

A behavior can optionally declare measurable numeric metrics that reference its existing semantic parameters:

```json
{
  "parameters": {
    "preferred_distance_m": 1.4,
    "stop_delay_ms": 350
  },
  "evaluation": {
    "metrics": [
      {
        "metric_id": "following_distance",
        "observable": "following_distance_m",
        "target_parameter": "preferred_distance_m",
        "unit": "m",
        "tolerance": 0.10,
        "zero_credit_at": 0.30,
        "weight": 2.0,
        "required": true
      }
    ]
  }
}
```

Robot observations are stored separately from the portable profile:

```json
{
  "behavior_id": "navigation.follow_person",
  "metrics": {
    "following_distance_m": 1.37,
    "stop_delay_ms": 372
  }
}
```

### Numeric scoring v0.1

For absolute error `e`, tolerance `t`, and zero-credit deviation `z`:

```text
e <= t      → similarity 1.0
t < e < z   → linear falloff from 1.0 to 0.0
e >= z      → similarity 0.0
```

The final observed score uses both metric weight and the behavior preservation-priority weight.

Missing required observations are explicit failures. Missing optional observations remain visible but are excluded from the score denominator.

Run the bundled example:

```bash
rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json
```

JSON mode:

```bash
rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json \
  --json
```

See [`docs/OBSERVED_EVALUATION.md`](docs/OBSERVED_EVALUATION.md).

## ROS 2 reference adapter

RCL's first middleware integration keeps ROS-specific details outside the portable profile:

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

The reference target is a ROS 2 Lyrical mobile base using `geometry_msgs/msg/Twist` for planar velocity. Semantic styles are mapped relative to the **target robot's declared limits**, rather than copying source motor percentages.

The ROS runtime dependency is lazy: importing and unit-testing the adapter does not require ROS 2 to be installed.

See [`docs/ROS2_REFERENCE_ADAPTER.md`](docs/ROS2_REFERENCE_ADAPTER.md).

## Adapter conformance

A zero-argument Python adapter can run against the published mobile-base fixture:

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

The suite deliberately removes capabilities in negative cases. An adapter that silently reports missing required capabilities as `preserved` fails conformance.

This is **experimental protocol conformance**, not physical robot safety certification or identity proof. See [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

## Declared score vs observed score

RCL intentionally keeps these separate:

**Declared Behavior Continuity Score** asks:

> Can the target embodiment represent the semantic behavior, and how much degradation did the adapter declare?

**Observed Continuity Score** asks:

> Given actual measured Robot B behavior, how close was it to the declared semantic target and tolerance?

The current observed evaluator is **observed-vs-declared**, not yet a full repeated-trial Robot A vs Robot B statistical equivalence test.

## Core principles

1. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
2. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
3. **User-owned and portable** — continuity should export without requiring a vendor cloud.
4. **Graceful degradation** — unsupported behavior must be reported, never silently called preserved.
5. **Declared and observed continuity are different** — representability is not proof of real execution fidelity.
6. **Observable continuity** — migration quality should be measurable and inspectable.
7. **Safety outranks continuity** — a legacy behavior never overrides target safety constraints.
8. **Scores do not define identity** — continuity scores measure declared or observed behavior, not personhood.

## Experimental compatibility levels

| Level | Meaning |
|---|---|
| **RCL Profile Compatible** | Can read, validate, preserve, and write the portable profile format. |
| **RCL Migration Compatible** | Can translate semantic behavior, expose degradation, and produce a valid migration report. |
| **RCL Continuity Ready** | Future real-robot level with live capture, restore, repeated-trial observed evaluation, and broader conformance. |

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

rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json

rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
pytest -q
```

## Who should experiment with RCL?

RCL is currently most useful for:

- robotics developers working with multiple embodiments;
- ROS 2 and robot middleware developers;
- research labs studying behavior transfer or lifelong robotics;
- robot manufacturers and system integrators exploring hardware replacement or fleet migration;
- developers interested in long-lived personal robots and user-owned robot history.

The project is early enough that **design feedback is as valuable as code**.

## Contributing

Useful contributions include:

- reviewing the semantic behavior model;
- proposing capability registry additions with concrete interoperability use cases;
- implementing adapters for real or simulated robots;
- running the conformance suite against independent adapters;
- designing observed evaluation metrics and repeatable experiments;
- contributing Robot A / Robot B observation fixtures;
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
│   ├── OBSERVED_EVALUATION.md
│   └── ROS2_REFERENCE_ADAPTER.md
├── spec/
│   ├── capability-registry-v0.1.json
│   └── schemas/
│       ├── observations.schema.json
│       ├── observed-evaluation-report.schema.json
│       └── ...
├── examples/
│   ├── mobile-base/
│   ├── observations/
│   └── targets/
├── rcl/
│   ├── adapter.py
│   ├── capabilities.py
│   ├── conformance.py
│   ├── evaluation.py
│   ├── migration.py
│   ├── profile.py
│   └── score.py
├── rcl_ros2/
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective identity, emotional authenticity, or certified physical safety. It describes portable robot continuity data and provides explicit experimental measures of declared and observed behavior preservation.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
