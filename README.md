# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.3-dev**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an open specification and reference implementation for preserving a robot's **experience, preferences, semantic behavior, and skill history independently from its current hardware body**.

The project now separates five questions:

```text
What should survive?
        ↓
Portable semantic profile (.rcl)
        ↓
Can Robot B represent it?
        ↓
Migration Report + Declared Continuity Score
        ↓
Did Robot B hit the declared behavior target?
        ↓
Observed-vs-declared Evaluation
        ↓
Were Robot A and Robot B measured under comparable conditions?
        ↓
Experiment Context Gate
        ↓
Does Robot B behave statistically like Robot A over repeated trials?
        ↓
Statistical Continuity Evaluation
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
- evaluate single target observations against declared tolerances;
- compare repeated Robot A / Robot B empirical behavior distributions;
- require declared comparable experiment context before repeated-trial scoring;
- calculate experimental observed and statistical continuity scores.

Reference declared migration:

```text
Continuity Score: 88.33%
Migration Success: YES
- navigation.follow_person: preserved (similarity=1.00)
- navigation.pre_turn_observation: approximated (similarity=0.65)
```

## Capability Registry v0.1

Initial standard capability IDs:

```text
navigation.planar_velocity
perception.person_tracking
perception.forward_range
perception.directional_attention
```

Reserved RCL namespaces reject invented standard-looking IDs:

```text
perception.person_tracking   VALID
perception.telepathy         INVALID — reserved but unregistered
```

Independent implementations can experiment with:

```text
x.<owner>.<semantic_path>
```

Example:

```text
x.acme.stereo_person_tracking
```

Capabilities describe **what an embodiment can semantically provide**, not how it is implemented.

```bash
rcl capabilities list
rcl capabilities show perception.person_tracking
rcl capabilities validate x.acme.stereo_person_tracking
```

See [`docs/CAPABILITY_REGISTRY.md`](docs/CAPABILITY_REGISTRY.md).

## Behavior tolerance metadata

A behavior can declare measurable numeric metrics that reference its existing semantic parameters:

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
        "required": true,
        "min_trials": 5
      }
    ]
  }
}
```

`min_trials` is used by repeated-trial evaluation and defaults to 5 when omitted.

## Observed-vs-declared evaluation v0.1

A single Robot B observation can be evaluated against the declared semantic target.

```bash
rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json
```

For absolute error `e`, tolerance `t`, and zero-credit deviation `z`:

```text
e <= t      → similarity 1.0
t < e < z   → linear falloff from 1.0 to 0.0
e >= z      → similarity 0.0
```

See [`docs/OBSERVED_EVALUATION.md`](docs/OBSERVED_EVALUATION.md).

## Statistical Continuity Evaluation v0.2

RCL can compare repeated Robot A and Robot B measurements for the same semantic metric.

```text
Robot A repeated trials
        ↓
empirical distribution
        ↘
          exact 1D Wasserstein distance
        ↗
empirical distribution
        ↑
Robot B repeated trials
```

Run the bundled example:

```bash
rcl compare-trials \
  examples/mobile-base \
  examples/trials/demo-rover-a.trials.json \
  examples/trials/demo-rover-b.trials.json
```

The report includes sample counts, means, sample standard deviations, Wasserstein-1 distance, and similarity for each metric.

The distribution distance remains in the original metric unit. The same tolerance policy is therefore reused:

```text
W1 <= tolerance      → similarity 1.0
tolerance < W1 < z   → linear falloff
W1 >= z              → similarity 0.0
```

This catches cases where averages match but behavior shape differs:

```text
Robot A: 1.40, 1.40, 1.40, 1.40, 1.40
Robot B: 1.20, 1.20, 1.40, 1.60, 1.60

mean(A) = mean(B) = 1.40 m
```

The means match, but the empirical distributions do not.

See [`docs/STATISTICAL_CONTINUITY.md`](docs/STATISTICAL_CONTINUITY.md).

## Experiment Context / Measurement Protocol v0.1

Repeated-trial scoring is now gated by declared experiment context. A trial capture contains a shared protocol and session-specific context:

```json
{
  "experiment": {
    "protocol": {
      "protocol_id": "rcl.person_following.baseline",
      "protocol_version": "0.1",
      "comparison_fields": [
        "task_id",
        "environment_id",
        "subject_ref",
        "start_condition_id"
      ]
    },
    "context": {
      "session_id": "robot-a-session-001",
      "task_id": "follow-person-straight-5m",
      "environment_id": "demo-lab-a-layout-01",
      "subject_ref": "subject-demo-01",
      "start_condition_id": "stationary-2m-behind-subject",
      "software_ref": "controller@1.0",
      "adapter_ref": "adapter@1.0",
      "sensor_config_ref": "sensor-set@1"
    }
  }
}
```

Protocol ID/version and protocol-selected context fields must match before Wasserstein scoring. If they do not:

```text
Context Comparable: NO
Statistical Continuity Score: N/A
Status: context_mismatch
```

No distribution score is calculated. This reduces the risk of interpreting room, subject, task, or starting-condition differences as robot behavior differences.

If `comparison_fields` is omitted, the default strict key is:

```text
task_id
environment_id
start_condition_id
```

`software_ref`, `adapter_ref`, and `sensor_config_ref` are recorded as informational metadata by default because Robot A and Robot B may legitimately use different implementations.

See [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md) and [`examples/protocols/person-following-baseline.protocol.json`](examples/protocols/person-following-baseline.protocol.json).

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

See [`docs/ROS2_REFERENCE_ADAPTER.md`](docs/ROS2_REFERENCE_ADAPTER.md).

## Adapter conformance

```bash
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
```

Expected reference result:

```text
Profile      PASS
Adapter      PASS
Migration    PASS
Safety       PASS
Reporting    PASS

Result: RCL Migration Compatible (experimental v0.3)
```

This is experimental protocol conformance, not physical robot safety certification. See [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

## Three continuity measures

RCL intentionally keeps these concepts separate.

**Declared Behavior Continuity Score** asks:

> Can Robot B represent the semantic behavior, and how much degradation did the adapter declare?

**Observed Continuity Score v0.1** asks:

> Did a measured Robot B behavior stay close to the declared target?

**Statistical Continuity Score v0.2** asks:

> Across repeated measurements under declared comparable context, how close is Robot B's empirical behavior distribution to Robot A's?

None of these scores define identity, consciousness, personhood, or emotional authenticity.

## Core principles

1. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
2. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
3. **User-owned and portable** — continuity should export without requiring a vendor cloud.
4. **Graceful degradation** — unsupported behavior must be reported, never silently called preserved.
5. **Declared and measured continuity are different** — representability is not proof of execution fidelity.
6. **Repeated behavior matters** — one correct sample does not prove a stable behavioral pattern.
7. **Comparable context before statistics** — do not score Robot A vs Robot B distributions when declared test conditions do not match.
8. **Safety outranks continuity** — a legacy behavior never overrides target safety constraints.
9. **Scores do not define identity** — continuity scores only quantify declared or observed behavior preservation.

## Experimental compatibility levels

| Level | Meaning |
|---|---|
| **RCL Profile Compatible** | Can read, validate, preserve, and write the portable profile format. |
| **RCL Migration Compatible** | Can translate semantic behavior, expose degradation, and produce a valid migration report. |
| **RCL Continuity Ready** | Future real-robot level with live capture, restore, context-controlled repeated-trial evaluation, and broader conformance. |

These are experimental v0.x compatibility concepts, not a formal certification program. See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

rcl capabilities list
rcl validate examples/mobile-base

rcl migrate \
  examples/mobile-base \
  examples/targets/demo-rover-b.embodiment.json \
  --output /tmp/migration-report.json

rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json

rcl compare-trials \
  examples/mobile-base \
  examples/trials/demo-rover-a.trials.json \
  examples/trials/demo-rover-b.trials.json

rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
pytest -q
```

## Repository layout

```text
robot-continuity-layer/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── CAPABILITY_REGISTRY.md
│   ├── CONFORMANCE.md
│   ├── EXPERIMENT_PROTOCOL.md
│   ├── OBSERVED_EVALUATION.md
│   ├── STATISTICAL_CONTINUITY.md
│   └── ROS2_REFERENCE_ADAPTER.md
├── examples/
│   ├── mobile-base/
│   ├── observations/
│   ├── protocols/
│   ├── trials/
│   └── targets/
├── rcl/
│   ├── adapter.py
│   ├── capabilities.py
│   ├── conformance.py
│   ├── evaluation.py
│   ├── experiment_context.py
│   ├── statistical_evaluation.py
│   ├── migration.py
│   └── score.py
├── rcl_ros2/
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective identity, emotional authenticity, formal statistical equivalence in every behavioral dimension, physical identity of experimental environments, or certified physical safety. It provides explicit experimental measures of portable, declared, and observed robot behavior continuity.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
