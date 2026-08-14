# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.3-dev**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an open specification and reference implementation for preserving a robot's **experience, preferences, semantic behavior, skill history, and auditable behavioral evolution independently from its current hardware body**.

The project now separates seven questions:

```text
What should survive?
        ↓
Portable semantic profile (.rcl)
        ↓
How did this behavior evolve over time?
        ↓
Habit History + Profile Diff
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
        ↓
Does that similarity remain stable across multiple sessions?
        ↓
Repeated-Session Confidence / Uncertainty
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
- generate machine-readable migration reports and a declared Behavior Continuity Score;
- translate mobile-base continuity behavior through a ROS 2 reference adapter;
- run an executable adapter conformance suite;
- evaluate single observations against declared tolerances;
- compare repeated Robot A / Robot B empirical behavior distributions;
- require comparable experiment context before repeated-trial scoring;
- aggregate multiple comparable sessions with Student-t uncertainty reporting;
- record optional behavior habit/history metadata without changing the five-payload `.rcl` layout;
- compare two profile snapshots with a deterministic semantic diff.

Reference declared migration:

```text
Continuity Score: 88.33%
Migration Success: YES
- navigation.follow_person: preserved (similarity=1.00)
- navigation.pre_turn_observation: approximated (similarity=0.65)
```

## Behavior Habit History v0.1

RCL separates two questions that are easy to confuse.

`source` says **where a behavior came from**:

```text
configured
learned
imported
```

`habit.lifecycle` says **how established it has become**:

```text
configured → learning → stable → legacy
```

A behavior can therefore remain `source: learned` while moving from `learning` to `stable` and eventually `legacy`.

```json
{
  "behavior_id": "navigation.follow_person",
  "parameters": {
    "preferred_distance_m": 1.32,
    "stop_delay_ms": 420
  },
  "source": "learned",
  "habit": {
    "lifecycle": "stable",
    "first_observed_at": "2026-01-15T00:00:00Z",
    "stable_since": "2026-07-01T00:00:00Z",
    "events": [
      {
        "event_id": "follow-003",
        "observed_at": "2026-07-01T00:00:00Z",
        "event_type": "stabilized",
        "parameter_values": {
          "preferred_distance_m": 1.32,
          "stop_delay_ms": 420
        },
        "evidence_ref": "sessions/person-following-2026H1"
      }
    ]
  }
}
```

History is **descriptive, not executable**. The current canonical behavior is always the top-level `parameters` object. Loading a profile never replays history events or mutates current behavior.

`legacy` is also never a safety override.

See [`docs/HABIT_HISTORY.md`](docs/HABIT_HISTORY.md).

## Profile Diff v0.1

Compare two semantic profile snapshots:

```bash
rcl diff \
  examples/history/mobile-base-before \
  examples/history/mobile-base-after
```

The reference example reports changes such as:

```text
preferred_distance_m: 1.36 -> 1.32
stop_delay_ms: 380 -> 420
habit.lifecycle: learning -> stable
+ history follow-003 [stabilized]
+ history follow-004 [user_confirmed]
+ navigation.pre_turn_observation
```

The machine-readable diff covers:

- behaviors added / removed / modified;
- semantic parameter changes;
- preservation priority and mode changes;
- source, confidence, required-capability, and evaluation changes;
- habit lifecycle/timestamp changes;
- history events added or removed.

JSON mode:

```bash
rcl diff before-profile after-profile --json
```

Profile Diff is an audit tool, not a Continuity Score.

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

## Observed-vs-declared evaluation v0.1

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

RCL compares repeated Robot A and Robot B measurements using exact one-dimensional empirical Wasserstein-1 distance.

```bash
rcl compare-trials \
  examples/mobile-base \
  examples/trials/demo-rover-a.trials.json \
  examples/trials/demo-rover-b.trials.json
```

The distribution distance remains in the original metric unit:

```text
W1 <= tolerance      → similarity 1.0
tolerance < W1 < z   → linear falloff
W1 >= z              → similarity 0.0
```

This catches cases where averages match but the behavioral spread or shape differs.

See [`docs/STATISTICAL_CONTINUITY.md`](docs/STATISTICAL_CONTINUITY.md).

## Experiment Context / Measurement Protocol v0.1

Repeated-trial scoring is gated by declared experiment context. Protocol ID/version and protocol-selected fields must match before distribution scoring.

If they do not:

```text
Context Comparable: NO
Statistical Continuity Score: N/A
Status: context_mismatch
```

The default strict comparison key is:

```text
task_id
environment_id
start_condition_id
```

Protocols may additionally require `subject_ref` or `operator_ref`. Robot-internal metadata such as software, adapter, and sensor configuration is informational by default because different embodiments may legitimately use different implementations.

See [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md).

## Repeated-Session Confidence / Uncertainty v0.1

A single repeated-trial session can still be unusually good or bad. RCL can aggregate a comparable series of sessions while keeping every session equally weighted.

```bash
rcl compare-sessions \
  examples/mobile-base \
  examples/sessions/demo-rover-a-b.sessions.json
```

The experimental default is:

```text
min_sessions = 3
confidence_level = 0.95
```

For session scores `x1 ... xn`:

```text
mean = Σxi / n
s    = sample standard deviation
SE   = s / sqrt(n)
CI   = mean ± t(0.975, n-1) × SE
```

For three sessions, `df=2` and the two-sided 95% Student-t critical value is `4.303`, not `1.96`.

Required-metric failures, context mismatches, and cross-session experiment drift remain explicit instead of being hidden by an average.

v0.1 deliberately does **not define a universal acceptance threshold** for whether two robots are the same.

See [`docs/SESSION_CONFIDENCE.md`](docs/SESSION_CONFIDENCE.md).

## ROS 2 reference adapter

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

The reference target is a ROS 2 Lyrical mobile base using `geometry_msgs/msg/Twist` for planar velocity. Semantic styles are mapped relative to the target robot's declared limits rather than copying source motor percentages.

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

See [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

## Four continuity measures

RCL intentionally keeps these concepts separate.

**Declared Behavior Continuity Score** asks:

> Can Robot B represent the semantic behavior, and how much degradation did the adapter declare?

**Observed Continuity Score v0.1** asks:

> Did a measured Robot B behavior stay close to the declared target?

**Statistical Continuity Score v0.2** asks:

> Across repeated measurements under declared comparable context, how close is Robot B's empirical behavior distribution to Robot A's?

**Repeated-Session Confidence v0.1** asks:

> Across multiple comparable sessions, how stable is that statistical continuity estimate and how uncertain is its mean?

Habit history and Profile Diff describe behavioral evolution; they are not additional scores.

None of these constructs define identity, consciousness, personhood, or emotional authenticity.

## Core principles

1. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
2. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
3. **User-owned and portable** — continuity should export without requiring a vendor cloud.
4. **Graceful degradation** — unsupported behavior must be reported, never silently called preserved.
5. **History is descriptive, not executable** — historical events explain evolution but never silently mutate current behavior.
6. **Declared and measured continuity are different** — representability is not proof of execution fidelity.
7. **Repeated behavior matters** — one correct sample does not prove a stable behavioral pattern.
8. **Comparable context before statistics** — do not score distributions under mismatched declared conditions.
9. **Longitudinal uncertainty must be visible** — a high mean without session-to-session uncertainty is incomplete evidence.
10. **Safety outranks continuity** — a legacy behavior never overrides target safety constraints.
11. **Scores do not define identity** — continuity measures only quantify declared or observed behavior preservation.

## Experimental compatibility levels

| Level | Meaning |
|---|---|
| **RCL Profile Compatible** | Can read, validate, preserve, write, and inspect the portable profile format. |
| **RCL Migration Compatible** | Can translate semantic behavior, expose degradation, and produce a valid migration report. |
| **RCL Continuity Ready** | Future real-robot level with live capture, restore, portable habit history, context-controlled repeated evaluation, and broader conformance. |

These are experimental v0.x compatibility concepts, not a formal certification program. See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

rcl validate examples/mobile-base
rcl capabilities list

rcl diff \
  examples/history/mobile-base-before \
  examples/history/mobile-base-after

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

rcl compare-sessions \
  examples/mobile-base \
  examples/sessions/demo-rover-a-b.sessions.json

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
│   ├── HABIT_HISTORY.md
│   ├── OBSERVED_EVALUATION.md
│   ├── SESSION_CONFIDENCE.md
│   ├── STATISTICAL_CONTINUITY.md
│   └── ROS2_REFERENCE_ADAPTER.md
├── examples/
│   ├── history/
│   ├── mobile-base/
│   ├── observations/
│   ├── protocols/
│   ├── sessions/
│   ├── trials/
│   └── targets/
├── rcl/
│   ├── adapter.py
│   ├── capabilities.py
│   ├── conformance.py
│   ├── evaluation.py
│   ├── experiment_context.py
│   ├── history.py
│   ├── profile_diff.py
│   ├── session_evaluation.py
│   ├── statistical_evaluation.py
│   ├── migration.py
│   └── score.py
├── rcl_ros2/
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective identity, emotional authenticity, formal statistical equivalence in every behavioral dimension, physical identity of experimental environments, universal longitudinal acceptance thresholds, or certified physical safety. It provides explicit experimental constructs for portable, auditable, declared, observed, statistical, and longitudinal robot behavior continuity.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
