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
A new repeated behavior appears
        ↓
Lightweight Context + Action + Outcome experience
        ↓
Raw or compacted evidence
        ↓
What purpose might explain it?
        ↓
Intent Discovery / Intent Candidate
        ↓
Was the proposed purpose explicitly accepted?
        ↓
Intent Approval + new immutable snapshot
        ↓
What purpose is now declared for continuity?
        ↓
Behavior Intent / Goal Semantics
        ↓
Did later evidence change what we believe the behavior means?
        ↓
Intent Revision / Correction + append-only intent history
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
Can the new body use its native capability while keeping the familiar manner?
        ↓
Expression + Expressive Timing
        ↓
Did Robot B actually satisfy the declared goal conditions?
        ↓
Observed Intent Success
        ↓
Did Robot B reproduce declared/observed behavior closely?
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
HOW      -> embodiment adapter / target-native strategy
LOOKS    -> expression
TEMPO    -> expressive temporal style
HISTORY  -> habit / legacy / prior intent interpretations
```

Two continuity principles follow from that separation:

> **Use the new body. Preserve the old manner.**
>
> **Preserve the gesture, not the limitation.**

A V2 robot should use better sensors, motors, controllers, and wiring for the actual function. A familiar V1 gesture may still remain as a legacy expression. If V1 was slow only because of a motor or wiring limitation, V2 does not have to copy that delay. If the slow tempo itself became a recognized or user-valued mannerism, that temporal character can be preserved explicitly.

## What works today — v0.4-dev

The reference implementation can:

- validate and package portable `.rcl` profiles with SHA-256 integrity manifests;
- describe source and target embodiments through a shared capability vocabulary;
- migrate semantic behavior and report preserved / approximated / unsupported / safety-blocked results;
- calculate a declared Behavior Continuity Score;
- preserve and migrate **Behavior Intent / Goal Semantics** separately from visible expression;
- hard-fail migration when a `required` intent cannot be satisfied;
- preserve a familiar visible expression separately while allowing the target to use a newer functional strategy;
- describe portable expressive tempo / dwell / transition without embedding raw motor trajectories;
- naturalize source timing that came from actuator, gearing, wiring, controller, or power limitations;
- explicitly preserve deliberate timing when the temporal style itself is recognized or user-valued;
- keep historical source timing descriptive with `normative=false` rather than silently treating measured milliseconds as target commands;
- report expression timing separately as naturalized / preserved / approximated / unsupported / safety-blocked;
- evaluate a proposed intent hypothesis from generic context-action-outcome episodes without hardcoding a specific behavior;
- evaluate the same hypothesis from compatible action-stratified Experience Summary evidence without reconstructing fake episodes;
- keep raw and aggregate Intent Discovery evidence provenance explicit;
- generate an **Intent Candidate** or `insufficient_evidence` result without mutating a profile;
- explicitly approve an eligible Intent Candidate only into a new immutable snapshot;
- preserve discovered-intent provenance, candidate/report hashes, approval actor/time, and `causal_claim=false` with the declared intent;
- explicitly revise an already-declared Intent only through a new immutable snapshot;
- preserve each previous Intent snapshot in append-only `intent_history` with a validated SHA-256 revision chain;
- reject stale revision candidates, semantic no-op revisions, and tampered historical Intent snapshots;
- evaluate whether a source-style or target-native strategy actually satisfied the same declared Intent success condition;
- report required Intent failures separately from inconclusive and nonblocking preferred/advisory outcomes;
- support numeric/binary and higher-is-better/lower-is-better discovery outcomes;
- record lightweight semantic Experience Episodes without embedding raw media;
- compact long-lived experience into deterministic numeric/binary summaries during idle or charging windows;
- preserve source/provenance digests and longitudinal exemplar IDs while keeping compaction non-destructive;
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

A source robot may perform a visible action because of a body-specific limitation. RCL preserves the **purpose** independently from that source-body implementation.

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

Robot V2 may have a rear depth camera and satisfy the functional goal without needing the turn for sensing. That does **not** mean the familiar turn must automatically disappear. When the target can reproduce it safely, it may remain as a separate legacy expression after or alongside the target-native functional check.

A target that cannot reproduce the old visible expression may still produce:

```text
Intent:      PRESERVED
Strategy:    direct_rear_clearance_sensing
Expression:  UNSUPPORTED / optional
```

A target that can reproduce it may instead produce:

```text
Intent:      PRESERVED
Strategy:    direct_rear_clearance_sensing
Expression:  PRESERVED
```

In both cases, V2 inherited **why** V1 checked behind itself. In the second case it also retains the recognizable manner without forcing the old gesture to remain the functional sensing mechanism.

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

## Expressive Timing / Motion Style v0.1

RCL can preserve a familiar gesture without preserving the physical limitation that once made that gesture slow.

```text
V1 observed rearward turn
1400 ms
reason: actuator / wiring limitation
        ↓
portable temporal style
natural + brief dwell + smooth return
        ↓
V2 target-native timing
380 ms turn + 160 ms dwell + 360 ms return
        ↓
Expression Timing: NATURALIZED
```

Portable timing metadata lives under `expression.temporal_style`:

```json
{
  "tempo": "natural",
  "dwell": "brief",
  "transition": "smooth",
  "timing_policy": "naturalize",
  "legacy_significance": "recognized",
  "source_timing_observation": {
    "motion_duration_ms": 1400,
    "dwell_duration_ms": 220,
    "return_duration_ms": 1350,
    "normative": false
  },
  "source_artifacts": [
    {
      "artifact": "actuator_speed_limit",
      "effect": "slower_than_intended"
    },
    {
      "artifact": "wiring_constraint",
      "effect": "slower_than_intended"
    }
  ]
}
```

The historical `1400 ms` value is evidence, not a target command. `source_timing_observation.normative` is therefore required to be `false`.

Two timing policies are supported:

```text
naturalize
→ keep the recognizable gesture but realize it using target-native timing

preserve_style
→ keep the explicitly significant temporal manner itself
```

For example, if the slow glance itself became user-valued:

```text
tempo = deliberate
legacy_significance = user_valued
timing_policy = preserve_style
```

A faster V2 can still use its improved hardware while deliberately performing the glance at its own safe `deliberate` target tempo. `preserve_style` is rejected when the source timing is only `incidental`.

Target adapters map semantic timing classes to concrete safe timing. RCL does not define one universal “human speed,” does not default to maximum motor speed, and does not store a joint-trajectory DSL in the portable profile. If target bounds force a different timing, the result is `approximated`; if the expression timing is unsafe, it can be `blocked_for_safety` while the functional Intent remains preserved.

A normal V2 result can therefore be:

```text
Behavior:          PRESERVED
Intent:            PRESERVED
Functional HOW:    direct_rear_clearance_sensing
Expression:        PRESERVED
Expression Timing: NATURALIZED
```

The functional safety check can complete first with the new system. The familiar glance is continuity expression, not a prerequisite that delays the new safety mechanism.

See [`docs/EXPRESSIVE_TIMING.md`](docs/EXPRESSIVE_TIMING.md).

Reference fixtures:

```text
examples/expression-timing/naturalized-rearward-glance.json
examples/expression-timing/deliberate-rearward-glance.json
examples/targets/intent-demo-v2-expressive.embodiment.json
```

## Intent Discovery / Intent Candidate v0.1

Behavior Intent stores a declared purpose. Intent Discovery asks whether a new repeated behavior has enough evidence to review a proposed explanation for why it exists.

v0.1 intentionally separates **hypothesis proposal** from **evidence evaluation**:

```text
learning system / LLM / VLM / human
        ↓
proposed goal hypothesis
        ↓
RCL deterministic evidence engine
        ↓
Intent Candidate
```

The core discovery engine does **not** contain behavior-specific goal hardcoding. The dataset declares one context, one candidate action, one outcome, and one proposed intent. The same engine compares action-present and action-absent episodes.

Numeric example:

```bash
rcl discover-intent \
  examples/intent-discovery/object-release-stability.dataset.json
```

Unrelated binary example using the exact same engine:

```bash
rcl discover-intent \
  examples/intent-discovery/dock-alignment.dataset.json
```

Default common evidence gates are published at:

```text
spec/policies/intent-discovery-policy-v0.1.json
```

```text
context episodes       >= 10
action-present samples >= 4
action-absent samples  >= 4
action repeat rate     >= 0.30
beneficial effect      >= dataset minimum_meaningful_effect
```

`strong` is an evidence-strength label, not a probability that the proposed intent is true. Every report contains `causal_claim=false` because association is not causal proof.

Intent Discovery never writes `behavior.intent` and never approves a candidate. **Explicit Intent Approval** is the separate mutation boundary.

See [`docs/INTENT_DISCOVERY.md`](docs/INTENT_DISCOVERY.md).

## Summary-Aware Intent Discovery v0.1

Long-lived robots do not need to reload every raw episode for routine association checks if compaction preserved the required comparison evidence.

```text
raw Experience Episodes
        ↓
compact-experience
        ↓
Experience Summary
  ├─ combined outcomes
  └─ action_strata
       ├─ present outcomes
       └─ absent outcomes
        ↓
discover-intent-summary
        ↓
Intent Candidate
```

```bash
rcl discover-intent-summary \
  experience-summary.json \
  examples/intent-discovery/object-release-stability.summary-hypothesis.json
```

Raw and aggregate evidence share one scoring/gating core, but the report always declares `evidence_basis=raw|aggregate`. Legacy summaries that do not contain action-stratified outcome statistics remain valid storage/audit artifacts but are explicitly rejected for summary-aware discovery rather than being used to invent pseudo-episodes.

See [`docs/SUMMARY_INTENT_DISCOVERY.md`](docs/SUMMARY_INTENT_DISCOVERY.md).

## Explicit Intent Approval / Profile Patch v0.1

An Intent Candidate is still only a review hypothesis. `approve-intent` explicitly accepts an eligible candidate into continuity data.

```text
Intent Candidate
  ↓
preview
  ↓
explicit approval
  ↓
new immutable snapshot
  ↓
Declared Intent + provenance
```

Preview:

```bash
rcl approve-intent preview \
  examples/intent-approval/object-release-before \
  candidate-report.json \
  interaction.post_release_hold \
  --approved-at 2026-08-14T09:00:00Z
```

Apply:

```bash
rcl approve-intent apply \
  examples/intent-approval/object-release-before \
  candidate-report.json \
  interaction.post_release_hold \
  /tmp/object-release-approved \
  --approved-at 2026-08-14T09:00:00Z \
  --approved-by local-user
```

v0.1 requires a schema-valid candidate, every evidence gate to pass, `candidate_action_id` to exactly match the target `behavior_id`, and the target behavior to have no existing intent. Existing intent replacement is deliberately rejected.

The source profile is never overwritten. Approval means the reviewed engineering hypothesis was selected for continuity; it does **not** turn observational association into causal proof.

See [`docs/INTENT_APPROVAL.md`](docs/INTENT_APPROVAL.md).

## Intent Revision / Correction v0.1

An approved Intent is the current engineering interpretation, not an eternal truth. Long-lived use may produce better evidence and justify a correction.

```text
Declared Intent v1
        ↓
new evidence
        ↓
Revision Candidate
        ↓
preview
        ↓
explicit approval
        ↓
Declared Intent v2
        ↓
Intent v1 retained in intent_history
```

Preview:

```bash
rcl revise-intent preview \
  PROFILE \
  revision-candidate.json \
  safety.pre_sit_clearance_check \
  --approved-at 2026-08-15T01:00:00Z
```

Apply:

```bash
rcl revise-intent apply \
  PROFILE \
  revision-candidate.json \
  safety.pre_sit_clearance_check \
  PROFILE_REVISED \
  --approved-at 2026-08-15T01:00:00Z \
  --approved-by local-user
```

Revision requires an existing declared Intent. The candidate carries the exact SHA-256 of that current Intent, so a candidate becomes stale if the profile changes before approval.

Every accepted correction appends an entry to `behavior.intent_history` containing the exact previous Intent snapshot, revision reason, evidence references, approval metadata, and from/to Intent digests. Multiple revisions must form a continuous digest chain ending at the current `behavior.intent` hash.

The replacement receives fresh `source=revised` provenance. Previous provenance remains inside the historical snapshot. Semantic behavior parameters, habit metadata, visible expression, source/confidence, identity, preferences, skills, and embodiment are unchanged.

Revision means a reviewer selected a better engineering interpretation given later evidence. It does **not** prove the old interpretation objectively false or the new one causally true.

See [`docs/INTENT_REVISION.md`](docs/INTENT_REVISION.md).

## Lightweight Experience Store + Compaction v0.1

RCL does not require a robot to retrain a model continuously just to preserve experience. Normal operation can record small semantic events while longitudinal analysis runs later.

```text
real-time control / perception
        ↓
semantic event
Context + Action + Outcome
        ↓
Experience Store
        ↓
idle / charging window
        ↓
compact-experience
        ↓
long-lived aggregate evidence
        ↓
Habit / Intent analysis
```

A compact episode can contain an optional external evidence reference without embedding raw video/audio/image bytes:

```json
{
  "episode_id": "release-001",
  "observed_at": "2026-08-10T09:00:00Z",
  "context": {
    "task": "object_release",
    "surface": "table"
  },
  "action": {
    "action_id": "interaction.post_release_hold",
    "performed": true,
    "parameters": {
      "duration_ms": 420
    }
  },
  "outcomes": {
    "object_stability": 0.96,
    "object_settled": true
  },
  "evidence_refs": ["sensor://release-001"]
}
```

Compaction is generic. Episodes are grouped by exact semantic context, action ID, and outcome-key set. Numeric outcomes retain count / mean / sample standard deviation / min / max; binary outcomes retain true/false counts and true rate. New summaries also retain action-stratified outcome aggregates needed for summary-aware Intent Discovery.

```bash
rcl compact-experience \
  examples/experience/mixed-robot-life.episodes.json \
  --output /tmp/experience-summary.json
```

Every v0.1 summary contains `destructive=false`. Compaction never deletes source episodes and never interprets summary creation as consent to prune evidence.

See [`docs/EXPERIENCE_STORE.md`](docs/EXPERIENCE_STORE.md).

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

Profile Diff reports behavior, parameter, preservation, history, **intent**, **intent provenance**, **intent revision history**, **expression**, and **expressive temporal-style** changes. It is an audit tool, not a Continuity Score.

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

## Observed Intent Success v0.1

Observed Intent Success evaluates **purpose achievement**, not source-motion imitation.

```text
V1 rearward check
  ↓
state.sitting_area_clear = satisfied
  => PASS

V2 direct rear depth sensing
  ↓
state.sitting_area_clear = satisfied
  => PASS
```

```bash
rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json
```

Per-intent statuses are `pass`, `fail`, `not_observable`, and `not_triggered`. A required Intent failure makes the report `failed`; a missing/unobservable/untriggered required Intent makes it `inconclusive`; preferred/advisory failures remain explicit but nonblocking.

`strategy_id` is audit metadata only and never participates in pass/fail logic. v0.1 deliberately introduces no universal success-rate threshold.

See [`docs/OBSERVED_INTENT_SUCCESS.md`](docs/OBSERVED_INTENT_SUCCESS.md).

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

**Experience Store / Compaction** records and summarizes neutral semantic evidence. It is a storage/evidence optimization layer, not a learning claim.

**Intent Discovery** asks whether observed context-action-outcome association is strong enough to review a proposed goal hypothesis. It does not assert causality or mutate the profile.

**Summary-Aware Intent Discovery** evaluates compatible aggregate evidence through the same discovery gates while keeping the aggregate evidence basis explicit.

**Explicit Intent Approval** is the reviewed mutation that converts an eligible Intent Candidate into declared continuity data in a new snapshot. It is not causal proof.

**Intent Revision / Correction** is the reviewed mutation that replaces an existing declared engineering interpretation while preserving the previous interpretation in append-only history.

**Behavior Intent** asks whether the target can represent the declared purpose, trigger, and success condition.

**Expression** asks whether a recognizable source-body gesture can also be retained independently from its functional necessity.

**Expressive Timing** asks what recognizable temporal character that expression should retain, while distinguishing target-native timing from historical hardware delay.

**Observed Intent Success** asks whether the declared success condition was actually observed as satisfied on a robot, independently from how that robot physically achieved it.

**Declared Behavior Continuity Score** asks whether Robot B can represent the semantic behavior.

**Observed Continuity Score v0.1** asks whether measured behavior stayed close to the declared target.

**Statistical Continuity Score v0.2** compares empirical behavior distributions.

**Repeated-Session Confidence v0.1** reports longitudinal uncertainty.

**Habit History**, **Profile Diff**, **Habit Promotion**, and **Explicit Habit Approval** are audit/review/mutation constructs, not extra identity scores.

None of these constructs define consciousness, personhood, subjective identity, or subjective motivation.

## Core principles

1. **Preserve why before copying how** — portable goal semantics outrank source-body implementation details.
2. **Use the new body; preserve the old manner** — improved target capabilities should perform the function, while familiar expressions may remain where safe and representable.
3. **Preserve the gesture, not the limitation** — source actuator, wiring, gearing, power, or controller delay is not automatically a target timing requirement.
4. **Purpose success is not motion similarity** — a target may use a different strategy and still satisfy the same declared success condition.
5. **Evidence before assertion** — a discovered intent is a review hypothesis until explicitly accepted; association is not causal proof.
6. **Intent approval is explicit** — discovery may recommend a goal, but only an explicit approval operation may add it to continuity data.
7. **Corrections preserve history** — later evidence may revise a declared purpose, but previous Intent snapshots are retained rather than silently erased.
8. **Log light, analyze later** — normal robot operation should record compact semantic events; longitudinal aggregation can run during idle or charging windows.
9. **Compaction is not deletion** — an experience summary never authorizes pruning source evidence.
10. **Semantic before kinematic** — preserve observable intent and style, not canonical raw motor values.
11. **Body-independent where possible** — hardware execution belongs in embodiment adapters.
12. **Expression is not purpose** — a recognizable motion may be preserved separately, but it never substitutes for a required functional goal.
13. **Timing observations are descriptive by default** — measured source milliseconds are history, not portable commands; intentionally preserved tempo must be represented semantically.
14. **Model-independent core** — LLM/VLM/foundation-model proposers may suggest hypotheses, but the RCL evidence format and evaluator do not depend on one AI model.
15. **User-owned and portable** — continuity should export without requiring a vendor cloud.
16. **Graceful degradation** — unsupported behavior must be reported, never silently called preserved.
17. **History is descriptive, not executable** — historical events and historical Intent snapshots explain evolution but never silently override current behavior.
18. **Promotion is advisory, not mutating** — evidence can create a review candidate but cannot silently change lifecycle state.
19. **Approval is explicit and immutable-by-default** — reviewed continuity mutations create new validated snapshots rather than overwriting the source.
20. **Declared, observed, and functional success are different** — representability, motion fidelity, and goal achievement are separate evaluation questions.
21. **Comparable context before statistics** — do not score distributions under mismatched declared conditions.
22. **Safety outranks continuity** — a legacy expression, temporal style, approved intent, revised intent, or observed-success result never overrides target safety constraints.
23. **Scores do not define identity** — continuity measures quantify declared or observed behavior preservation only.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

rcl validate examples/mobile-base
rcl capabilities list

rcl compact-experience \
  examples/experience/mixed-robot-life.episodes.json \
  --output /tmp/experience-summary.json

rcl discover-intent \
  examples/intent-discovery/object-release-stability.dataset.json \
  --output /tmp/intent-candidate.json

rcl discover-intent-summary \
  /tmp/experience-summary.json \
  examples/intent-discovery/object-release-stability.summary-hypothesis.json

rcl approve-intent preview \
  examples/intent-approval/object-release-before \
  /tmp/intent-candidate.json \
  interaction.post_release_hold \
  --approved-at 2026-08-14T09:00:00Z

rcl revise-intent preview \
  examples/intent/sit-assistant-v1 \
  revision-candidate.json \
  safety.pre_sit_clearance_check \
  --approved-at 2026-08-15T01:00:00Z

rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json

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

## Repository layout

```text
robot-continuity-layer/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── BEHAVIOR_INTENT.md
│   ├── EXPERIENCE_STORE.md
│   ├── EXPRESSIVE_TIMING.md
│   ├── INTENT_APPROVAL.md
│   ├── INTENT_DISCOVERY.md
│   ├── INTENT_REVISION.md
│   ├── SUMMARY_INTENT_DISCOVERY.md
│   ├── CAPABILITY_REGISTRY.md
│   ├── CONFORMANCE.md
│   ├── EXPERIMENT_PROTOCOL.md
│   ├── HABIT_APPROVAL.md
│   ├── HABIT_HISTORY.md
│   ├── HABIT_PROMOTION.md
│   ├── OBSERVED_EVALUATION.md
│   ├── OBSERVED_INTENT_SUCCESS.md
│   ├── SESSION_CONFIDENCE.md
│   ├── STATISTICAL_CONTINUITY.md
│   └── ROS2_REFERENCE_ADAPTER.md
├── examples/
│   ├── experience/
│   ├── expression-timing/
│   ├── intent/
│   ├── intent-approval/
│   ├── intent-discovery/
│   ├── intent-observations/
│   ├── history/
│   ├── mobile-base/
│   ├── observations/
│   ├── policy/
│   ├── protocols/
│   ├── sessions/
│   ├── trials/
│   └── targets/
├── rcl/
│   ├── experience.py
│   ├── expression_timing.py
│   ├── intent.py
│   ├── intent_approval.py
│   ├── intent_approval_cli.py
│   ├── intent_discovery.py
│   ├── intent_revision.py
│   ├── intent_revision_cli.py
│   ├── intent_success_evaluation.py
│   ├── intent_success_cli.py
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

RCL does **not** claim to measure consciousness, personhood, subjective motivation, free will, emotional authenticity, causal truth from observational association, universal statistical equivalence, universal habit thresholds, one universal natural movement speed, or certified physical safety.

Behavior Intent represents declared engineering goal semantics. Expression and Expressive Timing can preserve recognizable manner without turning source hardware defects into target requirements. Historical timing observations are descriptive and must remain non-normative. Intent Discovery produces an association-backed engineering hypothesis for review. Summary-Aware Intent Discovery evaluates compatible aggregate evidence without pretending it is raw observation. Explicit Intent Approval records a reviewed selection. Intent Revision records a reviewed correction while preserving the earlier interpretation. Observed Intent Success records whether a declared success condition was observed, independently from physical strategy, but it is not safety certification or proof of subjective purpose. Experience Compaction summarizes neutral evidence without retraining models or authorizing deletion. None of these means the robot experiences or understands a goal or gesture in a human subjective sense.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
