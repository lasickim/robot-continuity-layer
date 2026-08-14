# Robot Continuity Layer (RCL)

**Experimental open specification · draft v0.4-dev**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an open specification and reference implementation for preserving a robot's **experience, preferences, semantic behavior, behavioral history, and declared goals independently from its current hardware body**.

The `.rcl` package format remains backward-compatible with the existing five-payload layout. v0.4-dev extends the semantic meaning carried inside those payloads rather than introducing a new archive format.

## The continuity questions RCL separates

```text
What should survive?
        ↓
Portable semantic profile (.rcl)
        ↓
Why does this behavior exist?
        ↓
Behavior Intent / Goal Semantics
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
Can Robot B represent the behavior and its required goals?
        ↓
Migration + Declared Continuity
        ↓
Did Robot B actually reproduce it?
        ↓
Observed / Statistical / Repeated-Session Evaluation
```

## Why RCL exists

Raw joint angles, motor percentages, topic names, sensor layouts, and vendor-specific settings do not transfer cleanly between different robots.

RCL therefore prefers portable semantics:

```yaml
handover:
  approach_style: gentle
  preferred_distance_m: 0.55
  wait_for_grasp: true
```

An embodiment adapter decides how the target body can reproduce the behavior and must report degradation explicitly.

v0.4 adds another important separation:

```text
WHY      -> intent
WHAT     -> semantic behavior + parameters
HOW      -> embodiment adapter / target strategy
LOOKS    -> expression
HISTORY  -> habit / legacy
```

## What works today — v0.4-dev

The reference implementation can:

- validate and package portable `.rcl` profiles with SHA-256 integrity manifests;
- describe source and target embodiments through a shared capability vocabulary;
- migrate semantic behavior and report preserved / approximated / unsupported / safety-blocked results;
- calculate a declared Behavior Continuity Score;
- preserve and migrate **Behavior Intent / Goal Semantics** separately from visible expression;
- hard-fail migration when a `required` intent cannot be satisfied;
- allow an obsolete optional expression to disappear while the functional goal remains preserved;
- translate mobile-base behavior through a ROS 2 Lyrical reference adapter;
- run executable adapter conformance checks;
- evaluate single observations against declared tolerances;
- compare Robot A / Robot B repeated-trial distributions;
- require comparable experiment context before statistical scoring;
- aggregate comparable sessions with Student-t uncertainty reporting;
- record optional behavior habit/history metadata without changing the five-payload `.rcl` layout;
- compare two profile snapshots with deterministic semantic diffing;
- generate non-mutating habit lifecycle promotion candidates from explicit versioned evidence gates;
- preview explicit lifecycle approval as a deterministic patch;
- apply an approved lifecycle transition only into a new validated snapshot while keeping semantic behavior parameters unchanged.

## Behavior Intent / Goal Semantics v0.1

A source robot may perform a visible action because of a body-specific limitation. RCL should preserve the **purpose** rather than blindly copying the motion.

Example: Robot V1 looks behind before sitting because it needs to inspect the sitting area.

```text
V1 visible motion
    rearward observation

Functional intent
    verify sitting area is clear
```

A portable declaration can separate the two:

```json
{
  "behavior_id": "safety.pre_sit_clearance_check",
  "intent": {
    "goal_id": "safety.verify_sitting_area_clear",
    "trigger": "activity.before_sit_down",
    "success_condition": "state.sitting_area_clear",
    "failure_action": "block",
    "criticality": "required",
    "required_capabilities": [
      "perception.sitting_area_clearance"
    ]
  },
  "expression": {
    "expression_id": "observation.brief_rearward_check",
    "preservation_priority": "optional",
    "required_capabilities": [
      "perception.directional_attention"
    ]
  }
}
```

Robot V2 may have a rear depth camera and satisfy the goal without turning:

```text
Intent:      PRESERVED
Strategy:    direct_rear_clearance_sensing
Expression:  UNSUPPORTED / optional
```

That is a valid continuity result. The V2 robot inherited **why** V1 checked behind itself without being forced to imitate an obsolete body motion.

The same model applies to a wrist rotation before handover:

```text
WHY
interaction.optimize_handover_orientation

V1 LOOKS
brief wrist roll

V2 HOW
native arm/grasp orientation
```

The machine-readable goal vocabulary is published at:

```text
spec/intent-vocabulary-v0.1.json
```

Initial standard goals:

```text
safety.verify_sitting_area_clear
interaction.optimize_handover_orientation
```

Initial semantic capabilities added for these goals:

```text
perception.sitting_area_clearance
manipulation.handover_orientation
```

Unknown standard-looking goal IDs are rejected. Experimental goals may use `x.<owner>.<semantic_path>`.

A `required` intent is a hard migration gate. Optional/preferred expression loss does not by itself make migration fail.

See [`docs/BEHAVIOR_INTENT.md`](docs/BEHAVIOR_INTENT.md).

Reference fixture:

```text
examples/intent/sit-assistant-v1
examples/targets/intent-demo-v2.embodiment.json
rcl.intent_reference_adapter.IntentReferenceAdapter
```

## Behavior Habit History v0.1

RCL separates behavior origin from habit maturity.

`source` says where a behavior came from:

```text
configured
learned
imported
```

`habit.lifecycle` says how established it has become:

```text
configured → learning → stable → legacy
```

History is **descriptive, not executable**. Current top-level `parameters` remain canonical. Historical events never silently replay commands or override safety.

See [`docs/HABIT_HISTORY.md`](docs/HABIT_HISTORY.md).

## Profile Diff v0.1

```bash
rcl diff \
  examples/history/mobile-base-before \
  examples/history/mobile-base-after
```

Profile Diff reports behavior, parameter, preservation, history, **intent**, and **expression** changes. It is an audit tool, not a Continuity Score.

## Habit Promotion Policy v0.1

Habit Promotion asks whether declared history plus supporting repeated-session evidence is strong enough to **review** the next lifecycle transition.

```bash
rcl habit-candidates \
  examples/history/mobile-base-before \
  examples/policy/demo-follow-person.session-report.json
```

The evaluator never mutates the profile. Default thresholds are published in:

```text
spec/policies/habit-promotion-policy-v0.1.json
```

See [`docs/HABIT_PROMOTION.md`](docs/HABIT_PROMOTION.md).

## Explicit Habit Approval / Profile Patch v0.1

A promotion candidate is only a recommendation. Lifecycle changes require explicit approval.

Preview:

```bash
rcl approve-habit preview \
  my-profile \
  promotion-report.json \
  navigation.follow_person \
  --approved-at 2026-08-14T06:00:00Z
```

Apply into a new snapshot:

```bash
rcl approve-habit apply \
  my-profile \
  promotion-report.json \
  navigation.follow_person \
  my-profile-approved \
  --approved-at 2026-08-14T06:00:00Z
```

The source profile is never overwritten. The output receives a fresh manifest and is revalidated.

See [`docs/HABIT_APPROVAL.md`](docs/HABIT_APPROVAL.md).

## Capability Registry v0.1

Current standard capabilities include:

```text
navigation.planar_velocity
perception.person_tracking
perception.forward_range
perception.directional_attention
perception.sitting_area_clearance
manipulation.handover_orientation
```

Vendor/experimental extensions use:

```text
x.<owner>.<semantic_path>
```

```bash
rcl capabilities list
rcl capabilities show perception.sitting_area_clearance
rcl capabilities validate x.acme.stereo_person_tracking
```

See [`docs/CAPABILITY_REGISTRY.md`](docs/CAPABILITY_REGISTRY.md).

## Observed-vs-declared evaluation v0.1

```bash
rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json
```

Numeric tolerance scoring uses full credit inside tolerance, linear falloff, then zero credit beyond the declared limit.

See [`docs/OBSERVED_EVALUATION.md`](docs/OBSERVED_EVALUATION.md).

## Statistical Continuity Evaluation v0.2

RCL compares repeated Robot A and Robot B measurements using exact one-dimensional empirical Wasserstein-1 distance.

```bash
rcl compare-trials \
  examples/mobile-base \
  examples/trials/demo-rover-a.trials.json \
  examples/trials/demo-rover-b.trials.json
```

This catches cases where averages match but behavioral spread or distribution shape differs.

See [`docs/STATISTICAL_CONTINUITY.md`](docs/STATISTICAL_CONTINUITY.md).

## Experiment Context / Measurement Protocol v0.1

Repeated-trial scoring requires declared comparable experiment context.

```text
Context Comparable: NO
Statistical Continuity Score: N/A
Status: context_mismatch
```

See [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md).

## Repeated-Session Confidence / Uncertainty v0.1

```bash
rcl compare-sessions \
  examples/mobile-base \
  examples/sessions/demo-rover-a-b.sessions.json
```

Comparable sessions are equal-weight units and use a 95% Student-t confidence interval. Failures and context drift remain explicit instead of being hidden by an average.

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
```

ROS-specific execution details remain outside the portable profile.

See [`docs/ROS2_REFERENCE_ADAPTER.md`](docs/ROS2_REFERENCE_ADAPTER.md).

## Adapter conformance

```bash
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
```

This is experimental protocol conformance, not physical safety certification.

See [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

## Continuity measures and semantic facets

RCL intentionally keeps these concepts separate.

**Declared Behavior Continuity Score** asks whether Robot B can represent the semantic behavior.

**Behavior Intent** asks whether the target can preserve the declared purpose, trigger, and success condition.

**Expression** asks whether a recognizable source-body motion can also be retained.

**Observed Continuity Score v0.1** asks whether measured behavior stayed close to the declared target.

**Statistical Continuity Score v0.2** compares empirical behavior distributions.

**Repeated-Session Confidence v0.1** reports longitudinal uncertainty.

**Habit History**, **Profile Diff**, **Habit Promotion**, and **Explicit Habit Approval** are audit/review/mutation constructs, not extra identity scores.

None of these constructs define consciousness, personhood, or subjective identity.

## Core principles

1. **Preserve why before copying how** — portable goal semantics outrank source-body implementation details.
2. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
3. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
4. **Expression is not purpose** — a recognizable motion may be preserved separately, but it never substitutes for a required functional goal.
5. **User-owned and portable** — continuity should export without requiring a vendor cloud.
6. **Graceful degradation** — unsupported behavior must be reported, never silently called preserved.
7. **History is descriptive, not executable** — historical events explain evolution but never silently mutate current behavior.
8. **Promotion is advisory, not mutating** — evidence can create a review candidate but cannot silently change lifecycle state.
9. **Approval is explicit and immutable-by-default** — lifecycle mutation creates a new validated snapshot.
10. **Declared and measured continuity are different** — representability is not proof of execution fidelity.
11. **Comparable context before statistics** — do not score distributions under mismatched declared conditions.
12. **Safety outranks continuity** — a legacy expression never overrides target safety constraints.
13. **Scores do not define identity** — continuity measures quantify declared or observed behavior preservation only.

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

rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
pytest -q
```

Python intent migration example:

```python
import json
from pathlib import Path

from rcl.intent_reference_adapter import IntentReferenceAdapter
from rcl.migration import migrate_profile
from rcl.profile import RCLProfile

profile = RCLProfile.open("examples/intent/sit-assistant-v1")
target = json.loads(Path("examples/targets/intent-demo-v2.embodiment.json").read_text())
report = migrate_profile(profile, target, IntentReferenceAdapter())

print(report["behavior_results"][0]["intent_result"])
print(report["behavior_results"][0]["expression_result"])
```

## Repository layout

```text
robot-continuity-layer/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── BEHAVIOR_INTENT.md
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
│   ├── intent/
│   ├── history/
│   ├── mobile-base/
│   ├── observations/
│   ├── policy/
│   ├── protocols/
│   ├── sessions/
│   ├── trials/
│   └── targets/
├── rcl/
│   ├── intent.py
│   ├── intent_reference_adapter.py
│   ├── habit_approval.py
│   ├── habit_policy.py
│   ├── history.py
│   ├── migration.py
│   ├── profile_diff.py
│   └── ...
├── rcl_ros2/
└── tests/
```

## Important boundary

RCL does **not** claim to measure consciousness, personhood, subjective motivation, free will, emotional authenticity, universal statistical equivalence, universal habit thresholds, or certified physical safety.

Behavior Intent represents declared engineering goal semantics. Saying that RCL preserves a goal does not mean the robot experiences or understands that goal in a human subjective sense.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
