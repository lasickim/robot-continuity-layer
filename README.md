# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.3-dev**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an open specification and reference implementation for preserving a robot's **experience, preferences, semantic behavior, skill history, and auditable behavioral evolution independently from its current hardware body**.

The project now separates these questions:

```text
What should survive?
        ↓
Portable semantic profile (.rcl)
        ↓
How did this behavior evolve?
        ↓
Habit History + Profile Diff
        ↓
Is there enough evidence to review a habit-state promotion?
        ↓
Habit Promotion Policy
        ↓
Was that promotion explicitly approved?
        ↓
Habit Approval + new immutable snapshot
        ↓
Can Robot B represent the behavior?
        ↓
Migration + Declared Continuity
        ↓
Did Robot B actually reproduce it?
        ↓
Observed / Statistical / Repeated-Session Evaluation
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

- validate and package portable `.rcl` profiles with SHA-256 integrity manifests;
- describe source and target embodiments through a shared capability vocabulary;
- migrate semantic behavior and report preserved / approximated / unsupported / safety-blocked results;
- calculate a declared Behavior Continuity Score;
- translate mobile-base behavior through a ROS 2 Lyrical reference adapter;
- run executable adapter conformance checks;
- evaluate single observations against declared tolerances;
- compare Robot A / Robot B repeated-trial distributions;
- require comparable experiment context before statistical scoring;
- aggregate comparable sessions with Student-t uncertainty reporting;
- record optional behavior habit/history metadata without changing the five-payload `.rcl` layout;
- compare two profile snapshots with deterministic semantic diffing;
- generate **non-mutating habit lifecycle promotion candidates** from explicit versioned evidence gates;
- preview an explicit lifecycle approval as a deterministic patch;
- apply an approved lifecycle transition only into a new validated snapshot while keeping semantic behavior parameters unchanged.

## Behavior Habit History v0.1

RCL separates behavior origin from habit maturity.

`source` says **where the behavior came from**:

```text
configured
learned
imported
```

`habit.lifecycle` says **how established it has become**:

```text
configured → learning → stable → legacy
```

A behavior can remain `source: learned` while moving from `learning` to `stable` and eventually `legacy`.

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

History is **descriptive, not executable**. The current canonical behavior is always the top-level `parameters` object. Loading a profile never replays history events or mutates current behavior. `legacy` is never a safety override.

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

The machine-readable diff covers behavior add/remove/modify, semantic parameter changes, preservation/source/confidence changes, habit lifecycle changes, and history event additions/removals.

```bash
rcl diff before-profile after-profile --json
```

Profile Diff is an audit tool, not a Continuity Score.

## Habit Promotion Policy v0.1

Habit Promotion Policy asks whether the **declared evidence is strong enough to review the next lifecycle transition**.

```text
history + confidence + supporting repeated-session evidence
                         ↓
                 versioned gates
                         ↓
                candidate / blocked
                         ↓
                   human review
```

The evaluator never changes `behavior.parameters`, `habit.lifecycle`, timestamps, or history events.

Run the reference learning-profile example:

```bash
rcl habit-candidates \
  examples/history/mobile-base-before \
  examples/policy/demo-follow-person.session-report.json
```

Default `learning → stable` review gates include:

```text
source                         = learned
observation age                >= 30 days
history events                 >= 2
behavior confidence            >= 0.80
scorable repeated sessions     >= 3
session evaluation status      = estimated
mean continuity score          >= 90
between-session std            <= 5
95% score CI half-width        <= 5
qualifying behavior metrics    >= 1
metric mean similarity         >= 0.90
metric 95% CI half-width       <= 0.10
```

Default `stable → legacy` review is stricter: at least **5 scorable sessions**, **180 stable days**, and **explicit user confirmation**.

The thresholds are published in:

```text
spec/policies/habit-promotion-policy-v0.1.json
```

They are explicit versioned engineering defaults, not universal truths. A custom policy can be supplied with `--policy`.

Important boundary: habit history supplies formation evidence. The current Robot A ↔ Robot B repeated-session report supplies **supporting reproducibility evidence only**; it is not direct proof that a source habit formed by itself.

See [`docs/HABIT_PROMOTION.md`](docs/HABIT_PROMOTION.md).

## Explicit Habit Approval / Profile Patch v0.1

A promotion candidate is only a recommendation. Lifecycle state changes require a separate explicit approval operation.

Preview without modifying any files:

```bash
rcl approve-habit preview \
  my-profile \
  promotion-report.json \
  navigation.follow_person \
  --approved-at 2026-08-14T06:00:00Z \
  --approved-by local-user
```

Apply into a **new** snapshot directory:

```bash
rcl approve-habit apply \
  my-profile \
  promotion-report.json \
  navigation.follow_person \
  my-profile-approved \
  --approved-at 2026-08-14T06:00:00Z \
  --approved-by local-user
```

Approval re-validates that the promotion report is still an eligible candidate for the exact current lifecycle. It rejects stale reports, blocked decisions, backwards timestamps, existing output paths, and output paths inside the source profile.

Apply copies the five payloads, changes only the selected behavior's habit lifecycle/timestamp/history metadata, adds one deterministic `promotion_approved` audit event, regenerates `manifest.json` with fresh SHA-256 hashes, validates the new profile, runs Profile Diff, and rejects any semantic `behavior.parameters` change.

The source profile is never overwritten.

See [`docs/HABIT_APPROVAL.md`](docs/HABIT_APPROVAL.md).

## Capability Registry v0.1

Initial standard capability IDs:

```text
navigation.planar_velocity
perception.person_tracking
perception.forward_range
perception.directional_attention
```

Reserved RCL namespaces reject invented standard-looking IDs, while independent extensions use:

```text
x.<owner>.<semantic_path>
```

```bash
rcl capabilities list
rcl capabilities show perception.person_tracking
rcl capabilities validate x.acme.stereo_person_tracking
```

See [`docs/CAPABILITY_REGISTRY.md`](docs/CAPABILITY_REGISTRY.md).

## Observed-vs-declared evaluation v0.1

A behavior can declare numeric evaluation metrics referencing its semantic parameters.

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

```text
W1 <= tolerance      → similarity 1.0
tolerance < W1 < z   → linear falloff
W1 >= z              → similarity 0.0
```

This catches cases where averages match but behavioral spread or distribution shape differs.

See [`docs/STATISTICAL_CONTINUITY.md`](docs/STATISTICAL_CONTINUITY.md).

## Experiment Context / Measurement Protocol v0.1

Repeated-trial scoring is gated by declared experiment context. Protocol ID/version and protocol-selected fields must match before distribution scoring.

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

Protocols may additionally require `subject_ref` or `operator_ref`. Robot-internal software/adapter/sensor metadata is informational by default because different embodiments may legitimately use different implementations.

See [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md).

## Repeated-Session Confidence / Uncertainty v0.1

A single repeated-trial session can still be unusually good or bad. RCL aggregates comparable sessions while keeping every session equally weighted.

```bash
rcl compare-sessions \
  examples/mobile-base \
  examples/sessions/demo-rover-a-b.sessions.json
```

The experimental default is three sessions and a 95% Student-t confidence interval. For three sessions, `df=2` and the two-sided 95% critical value is `4.303`, not the large-sample normal value `1.96`.

Required-metric failures, context mismatches, and cross-session experiment drift remain explicit instead of being hidden by an average.

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

The reference target is a ROS 2 Lyrical mobile base using `geometry_msgs/msg/Twist`. ROS-specific execution details remain outside the portable RCL profile.

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

## Continuity measures and audit tools

RCL intentionally keeps these concepts separate.

**Declared Behavior Continuity Score** asks whether Robot B can represent the semantic behavior.

**Observed Continuity Score v0.1** asks whether a measured Robot B behavior stayed close to the declared target.

**Statistical Continuity Score v0.2** asks how close Robot B's empirical behavior distribution is to Robot A's under comparable context.

**Repeated-Session Confidence v0.1** asks how stable that continuity estimate remains across comparable sessions.

**Habit History**, **Profile Diff**, **Habit Promotion Policy**, and **Explicit Habit Approval** are audit/review/mutation constructs, not extra identity scores.

None of these constructs define identity, consciousness, personhood, or emotional authenticity.

## Core principles

1. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
2. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
3. **User-owned and portable** — continuity should export without requiring a vendor cloud.
4. **Graceful degradation** — unsupported behavior must be reported, never silently called preserved.
5. **History is descriptive, not executable** — historical events explain evolution but never silently mutate current behavior.
6. **Promotion is advisory, not mutating** — evidence can create a review candidate but cannot silently change lifecycle state.
7. **Approval is explicit and immutable-by-default** — lifecycle mutation creates a new validated snapshot rather than overwriting the source.
8. **Declared and measured continuity are different** — representability is not proof of execution fidelity.
9. **Repeated behavior matters** — one correct sample does not prove a stable behavioral pattern.
10. **Comparable context before statistics** — do not score distributions under mismatched declared conditions.
11. **Longitudinal uncertainty must be visible** — a high mean without session-to-session uncertainty is incomplete evidence.
12. **Safety outranks continuity** — a legacy behavior never overrides target safety constraints.
13. **Scores do not define identity** — continuity measures only quantify declared or observed behavior preservation.

## Experimental compatibility levels

| Level | Meaning |
|---|---|
| **RCL Profile Compatible** | Can read, validate, preserve, write, and inspect the portable profile format. |
| **RCL Migration Compatible** | Can translate semantic behavior, expose degradation, and produce a valid migration report. |
| **RCL Continuity Ready** | Future real-robot level with live capture, restore, portable habit history, reviewed promotion/approval, context-controlled repeated evaluation, and broader conformance. |

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

rcl habit-candidates \
  examples/history/mobile-base-before \
  examples/policy/demo-follow-person.session-report.json \
  --output /tmp/promotion-report.json

rcl approve-habit preview \
  examples/history/mobile-base-before \
  /tmp/promotion-report.json \
  navigation.follow_person \
  --approved-at 2026-08-14T06:00:00Z

rcl approve-habit apply \
  examples/history/mobile-base-before \
  /tmp/promotion-report.json \
  navigation.follow_person \
  /tmp/mobile-base-approved \
  --approved-at 2026-08-14T06:00:00Z

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
│   ├── HABIT_APPROVAL.md
│   ├── HABIT_HISTORY.md
│   ├── HABIT_PROMOTION.md
│   ├── OBSERVED_EVALUATION.md
│   ├── SESSION_CONFIDENCE.md
│   ├── STATISTICAL_CONTINUITY.md
│   └── ROS2_REFERENCE_ADAPTER.md
├── examples/
│   ├── history/
│   ├── mobile-base/
│   ├── observations/
│   ├── policy/
│   ├── protocols/
│   ├── sessions/
│   ├── trials/
│   └── targets/
├── rcl/
│   ├── habit_approval.py
│   ├── habit_policy.py
│   ├── history.py
│   ├── profile_diff.py
│   ├── session_evaluation.py
│   └── ...
├── rcl_ros2/
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective identity, emotional authenticity, universal statistical equivalence, universal habit-promotion thresholds, physical safety, or implied user consent. It provides explicit experimental constructs for portable, auditable, declared, observed, statistical, longitudinal, reviewable, and explicitly approved robot behavior continuity.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
