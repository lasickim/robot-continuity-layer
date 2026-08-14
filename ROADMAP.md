# RCL Roadmap

RCL is being developed from a small, testable continuity core toward real multi-robot interoperability. The roadmap is experimental and will change as real robot integrations expose weaknesses in the model.

## v0.2 — portable semantic migration

- [x] portable semantic continuity profile
- [x] `.rcl` package with integrity manifest
- [x] explicit Embodiment Adapter interface
- [x] semantic capability matching
- [x] migration report
- [x] Behavior Continuity Score
- [x] required-behavior failure rule
- [x] reference Robot A → Robot B dry-run migration
- [x] experimental compatibility levels
- [x] public contribution guide

## v0.3 — interoperability, evaluation, and habit lifecycle

Primary goal: make RCL testable, measurable, and capable of carrying auditable behavioral history without silently mutating the robot.

- [x] ROS 2 reference adapter (Lyrical mobile-base semantic bridge)
- [x] adapter conformance test kit
- [x] Capability Registry v0.1 and extension namespaces
- [x] migration-time capability vocabulary validation
- [x] numeric behavior tolerance and observation metadata
- [x] Observed Continuity Evaluation v0.1
- [x] Statistical Continuity Evaluation v0.2 using exact 1D empirical Wasserstein distance
- [x] Experiment Context / Measurement Protocol v0.1
- [x] Repeated-Session Confidence / Uncertainty v0.1
- [x] semantic Profile Diff v0.1
- [x] Behavior Habit History v0.1
- [x] configured → learning → stable → legacy lifecycle
- [x] Habit Promotion Policy v0.1
- [x] Explicit Habit Approval / Profile Patch v0.1
- [x] immutable approved snapshot creation with regenerated manifest

### v0.3 core boundary

v0.3 established the end-to-end behavior/history pipeline:

```text
profile
  ↓
migration
  ↓
observed / repeated evaluation
  ↓
habit history
  ↓
promotion candidate
  ↓
explicit approval
  ↓
new immutable snapshot
```

The package container remains the five-payload `.rcl` format.

## v0.4 — Behavior Intent / Goal Semantics

Primary goal: preserve **why** a behavior exists independently from the source body's physical strategy, preserve recognizable legacy manner without blindly copying hardware limitations, discover and explicitly approve reviewable purpose hypotheses, allow those interpretations to be corrected later without erasing history, measure whether a target actually satisfies the declared purpose, and keep long-lived experience storage lightweight enough for real robots.

- [x] optional `behavior.intent` block
- [x] portable goal / trigger / success-condition / failure-action model
- [x] required / preferred / advisory intent criticality
- [x] Behavior Intent vocabulary v0.1
- [x] standard goals for pre-sit clearance and handover orientation
- [x] semantic capabilities `perception.sitting_area_clearance` and `manipulation.handover_orientation`
- [x] optional visible `expression` facet separate from functional purpose
- [x] adapter-level intent and expression migration results
- [x] required-intent hard migration gate
- [x] reference V1 → V2 demo where intent is preserved while obsolete expressions are dropped
- [x] Profile Diff support for intent/expression changes
- [x] Expressive Timing / Motion Style v0.1
- [x] optional `expression.temporal_style` with tempo / dwell / transition semantics
- [x] `naturalize` versus `preserve_style` timing policy
- [x] source timing observations explicitly non-normative (`normative=false`)
- [x] source hardware-artifact provenance for motor/gearing/wiring/controller/power limitations
- [x] target-native timing realization with safety bounds
- [x] timing migration statuses `naturalized / preserved / approximated / unsupported / blocked_for_safety`
- [x] V1 hardware-limited 1400 ms → V2 naturalized 380 ms reference case
- [x] user-valued deliberate tempo preserved on faster target hardware
- [x] Profile Diff support for expressive temporal-style changes
- [x] Explicit Legacy Expression Optimization / Removal Approval v0.1
- [x] `simplify` / `remove` candidates bound to exact current-expression SHA-256
- [x] deterministic non-mutating optimization preview plus explicit immutable apply
- [x] append-only `behavior.expression_history` preserving complete previous expression snapshots
- [x] multi-change expression SHA-256 chain with canonical JSON-null terminal digest after removal
- [x] stale-candidate and semantic no-op simplification rejection
- [x] expressive timing and source hardware-artifact provenance retained after simplification/removal
- [x] `rcl optimize-expression preview|apply` CLI
- [x] Profile Diff support for expression-history changes
- [x] Intent Discovery Dataset v0.1 using generic context-action-outcome episodes
- [x] Intent Discovery Policy v0.1 with explicit sample/repetition gates
- [x] Intent Candidate Report v0.1 with `causal_claim=false`
- [x] generic deterministic numeric and binary outcome association engine
- [x] higher-is-better and lower-is-better outcome support
- [x] dataset-specific meaningful-effect thresholds
- [x] model-independent `rcl discover-intent` CLI
- [x] reference object-release and unrelated auto-docking discovery fixtures
- [x] strong/moderate evidence labels explicitly separated from probability claims
- [x] lightweight Experience Episode Set v0.1
- [x] deterministic non-destructive Experience Summary v0.1
- [x] generic semantic grouping by context + action + outcome shape
- [x] numeric and binary outcome compaction using dependency-light statistics
- [x] source/provenance digests plus early/late retained exemplars
- [x] `rcl compact-experience` CLI
- [x] explicit `destructive=false` compaction boundary; no automatic source deletion
- [x] action-stratified Experience Summary statistics for action-present/action-absent outcomes
- [x] summary-aware Intent Discovery from aggregate evidence without pseudo-episode reconstruction
- [x] shared raw/aggregate discovery scoring and gate logic
- [x] explicit raw-vs-aggregate Intent Candidate evidence provenance
- [x] `rcl discover-intent-summary` CLI
- [x] Explicit Intent Approval / Profile Patch v0.1
- [x] deterministic candidate-report and source-behavior SHA-256 provenance
- [x] immutable approved snapshot with `behavior.intent` provenance and `causal_claim=false`
- [x] `rcl approve-intent preview|apply` CLI
- [x] Intent Revision / Correction v0.1
- [x] append-only `behavior.intent_history` preserving complete previous Intent snapshots
- [x] multi-revision SHA-256 digest-chain and historical-snapshot tamper validation
- [x] stale-current-intent and semantic no-op revision rejection
- [x] revised-intent provenance with reason, evidence refs, approval actor/time, and `causal_claim=false`
- [x] `rcl revise-intent preview|apply` CLI
- [x] Profile Diff support for current Intent replacement plus Intent-history addition
- [x] Observed Intent Success v0.1 distinct from motion similarity
- [x] Intent Observation Input v0.1 with exact behavior/trigger/success-condition matching
- [x] pass / fail / not_observable / not_triggered intent-result statuses
- [x] required-intent failed / inconclusive aggregate rules without a universal success-rate threshold
- [x] target-native strategy audit metadata excluded from pass/fail logic
- [x] V1 source-style and V2 target-native fixtures satisfying the same declared intents
- [x] `rcl evaluate-intent` CLI
- [ ] optional proposer plugin interface for LLM/VLM/foundation-model or human-generated goal hypotheses
- [ ] intent-aware conformance checks for independently implemented adapters
- [ ] goal vocabulary proposal / review workflow
- [ ] richer alternative-capability / capability-set semantics for goals with multiple valid satisfaction paths
- [ ] repeated-trial / repeated-session statistical Intent Success evaluation
- [ ] stronger context-specificity / confound reporting beyond v0.1 association comparison
- [ ] explicit retention / prune / archive policy after verified compaction
- [ ] summary-aware Habit evidence evaluation with raw-vs-aggregate provenance distinction

### v0.4 semantic rule

```text
WHY      → intent
WHAT     → semantic behavior + parameters
HOW      → embodiment adapter / target-native functional strategy
LOOKS    → expression
TEMPO    → expressive temporal style
HISTORY  → habit / legacy / prior Intent and Expression interpretations
```

RCL's default continuity principle is:

```text
Use the new body.
Preserve the old manner.
Do not preserve the old limitation by accident.
Preserve by default; optimize only by explicit approval.
```

The target may perform the functional check with a newer system first, then reproduce a familiar legacy gesture separately. If source timing was slow only because of old hardware, the target may naturalize the gesture. If the temporal style itself became recognized or user-valued, it may be explicitly preserved.

A behavior becoming functionally unnecessary is not permission to forget it. Simplifying or removing an active legacy expression is a separate reviewed mutation. The current expression may change, but the exact prior expression remains in append-only `expression_history` with a validated digest chain.

A target may change HOW while preserving WHY, LOOKS, and recognizable TEMPO. If LOOKS cannot be safely reproduced, WHY remains higher priority.

Intent Discovery, Approval, Revision, Migration, Observed Intent Success, and Expression Optimization form auditable continuity lifecycles. Long-lived raw evidence can be compacted before discovery without pretending aggregate statistics are raw observations:

```text
experience
  ↓
optional non-destructive compaction
  ↓
raw OR aggregate context-action-outcome evidence
  ↓
shared Intent Discovery scoring
  ↓
Intent Candidate
  ↓
explicit review
  ↓
Intent Approval
  ↓
new immutable snapshot
  ↓
declared intent + provenance
  ↓
more experience / better evidence
  ↓
Revision Candidate
  ↓
explicit Intent Revision
  ↓
new current Intent + append-only previous Intent history
  ↓
migration to another embodiment
  ├─ target-native functional strategy
  ├─ legacy expression where safe/representable
  └─ target-native expressive timing realization
  ↓
Observed Intent Success
  ↓
optional Expression Optimization Candidate
  ↓
explicit simplify/remove approval
  ↓
new snapshot + append-only previous Expression history
  ↓
separate motion / statistical evaluation
```

An Intent Candidate is an association-backed engineering hypothesis, not causal proof or subjective motivation. Approval means the hypothesis was explicitly selected for continuity. Revision means later evidence led to an explicitly accepted better engineering interpretation. Observed Intent Success means the declared engineering success condition was observed during a controlled execution. Expressive Timing preserves temporal character without making source hardware delay canonical. Expression Optimization records a reviewed continuity decision without erasing the old manner from history. None of these operations proves causality, consciousness, or subjective purpose.

Long-lived experience handling is deliberately split by compute timescale:

```text
real-time / event time
  ↓
small semantic Experience Episode
  ↓
idle / charging window
  ↓
non-destructive compaction
  ↓
long-lived aggregate evidence
  ↓
summary-aware Intent Discovery / other longitudinal analysis
```

### v0.4 privacy/provenance follow-on

Long-lived intent/history profiles will also need stronger provenance and privacy controls:

- [ ] memory namespaces
- [ ] encrypted private sections
- [ ] profile signing
- [ ] provenance metadata beyond current experience / approval / revision digests
- [ ] selective export
- [ ] retained-history archival / deletion policy

## v0.5 — real robot reference migration

Primary goal: replace configuration-only similarity with measured physical behavior continuity across actual source and target robots.

- [ ] Robot A live behavior capture
- [ ] lightweight semantic experience logging on physical Robot A
- [ ] idle/charging-window compaction on physical hardware
- [ ] summary-aware Intent Discovery on physical aggregate evidence
- [ ] `.rcl` export
- [ ] Robot B restore
- [ ] measured before/after following behavior
- [ ] measured before/after manipulation behavior
- [ ] measured functional-intent success independently from visible expression similarity
- [ ] source-style versus target-native strategy Intent Success demo on physical robots
- [ ] physical demo of hardware-limited source timing naturalized on faster target actuators
- [ ] physical demo of user-valued deliberate timing preserved on faster hardware
- [ ] physical demo of explicit legacy-expression simplify/remove approval while preserving expression history
- [ ] live learned-habit capture and promotion demo
- [ ] live context-action-outcome capture for an emergent behavior
- [ ] real Intent Candidate generation from longitudinal robot data
- [ ] explicit human approval of a discovered Intent Candidate into a real snapshot
- [ ] later evidence causing an explicit real-world Intent revision while preserving the original interpretation
- [ ] multi-session Statistical Continuity Score on physical robots
- [ ] controlled experiment context capture from real sessions
- [ ] uncertainty and confidence reporting on real robot data
- [ ] user-reviewed habit promotion on real longitudinal evidence
- [ ] explicit approval creating a new real-robot profile snapshot
- [ ] video demo
- [ ] reproducible test procedure and dataset

## v0.6+ — ecosystem and governance experiments

- [ ] LeRobot integration experiment
- [ ] simulator reference adapters
- [ ] multiple independently maintained robot adapters
- [ ] cross-vendor migration demo
- [ ] migration report cross-implementation fixtures
- [ ] capability and intent vocabulary proposal / review workflow
- [ ] version negotiation
- [ ] backward-compatibility policy
- [ ] public adapter registry concept
- [ ] multi-party vocabulary governance experiment

## v1.0 target — stable continuity interoperability layer

- [ ] stable portable core specification
- [ ] stable capability and intent vocabularies with extension policy
- [ ] multi-vendor adapter ecosystem
- [ ] independent conformance suites for multiple embodiment classes
- [ ] measured continuity evaluation profile
- [ ] observed functional-intent success evaluation profile
- [ ] reproducible statistical evaluation protocol
- [ ] longitudinal uncertainty profile
- [ ] behavior-history portability profile
- [ ] expressive timing / temporal-style portability profile
- [ ] auditable expression-history / explicit expression-optimization profile
- [ ] lightweight long-lived experience storage / compaction profile
- [ ] explicit approved-mutation / snapshot profile
- [ ] functional-intent preservation profile
- [ ] model-independent raw/aggregate intent-discovery evidence profile
- [ ] explicit intent-candidate approval profile
- [ ] auditable Intent revision / prior-interpretation history profile
- [ ] compatibility/certification profile
- [ ] security and privacy profile
- [ ] stable extension mechanism
- [ ] governance model for an open standard

## Non-goals

RCL does not attempt to standardize every robot command, replace ROS 2 or other robot middleware, define consciousness/personhood/subjective motivation, infer causality from association alone, archive unlimited raw media, claim aggregate evidence can recover discarded raw observations, declare an approved/revised Intent to be eternal truth, equate Intent Success with source-motion similarity, copy source hardware defects as normative behavior, automatically erase a familiar expression merely because it became functionally redundant, define one universal natural motion speed, or force physically different embodiments to behave identically. Its scope is the portable representation, translation, lightweight experience evidence, history, declared purpose, recognizable expression and timing, reviewable purpose hypotheses, explicit approved continuity mutations, auditable corrections, and measurable preservation and observed satisfaction of robot continuity data.
