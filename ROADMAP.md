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

Primary goal: preserve **why** a behavior exists independently from the source body's physical strategy or recognizable motion, and begin discovering reviewable purpose hypotheses from new learned behavior.

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
- [x] Intent Discovery Dataset v0.1 using generic context-action-outcome episodes
- [x] Intent Discovery Policy v0.1 with explicit sample/repetition gates
- [x] Intent Candidate Report v0.1 with `causal_claim=false`
- [x] generic deterministic numeric and binary outcome association engine
- [x] higher-is-better and lower-is-better outcome support
- [x] dataset-specific meaningful-effect thresholds
- [x] model-independent `rcl discover-intent` CLI
- [x] reference object-release and unrelated auto-docking discovery fixtures
- [x] strong/moderate evidence labels explicitly separated from probability claims
- [ ] Explicit Intent Approval / Profile Patch that converts an accepted candidate into a new immutable snapshot
- [ ] optional proposer plugin interface for LLM/VLM/foundation-model or human-generated goal hypotheses
- [ ] intent-aware conformance checks for independently implemented adapters
- [ ] goal vocabulary proposal / review workflow
- [ ] richer alternative-capability / capability-set semantics for goals with multiple valid satisfaction paths
- [ ] observed intent-success evidence model distinct from motion similarity
- [ ] stronger context-specificity / confound reporting beyond v0.1 association comparison

### v0.4 semantic rule

```text
WHY      → intent
WHAT     → semantic behavior + parameters
HOW      → embodiment adapter / target strategy
LOOKS    → expression
HISTORY  → habit / legacy
```

A target may change HOW and lose an optional LOOKS expression while still preserving WHY.

Intent Discovery extends the lifecycle before intent is declared:

```text
experience
  ↓
pattern
  ↓
goal hypothesis
  ↓
context-action-outcome evidence
  ↓
Intent Candidate
  ↓
explicit review / future approval
  ↓
declared intent
  ↓
continuity
```

An Intent Candidate is an association-backed engineering hypothesis, not causal proof or subjective motivation.

### v0.4 privacy/provenance follow-on

Long-lived intent/history profiles will also need stronger provenance and privacy controls:

- [ ] memory namespaces
- [ ] encrypted private sections
- [ ] profile signing
- [ ] provenance metadata
- [ ] selective export
- [ ] retained-history compaction / archival policy

## v0.5 — real robot reference migration

Primary goal: replace configuration-only similarity with measured physical behavior continuity across actual source and target robots.

- [ ] Robot A live behavior capture
- [ ] `.rcl` export
- [ ] Robot B restore
- [ ] measured before/after following behavior
- [ ] measured before/after manipulation behavior
- [ ] measured functional-intent success independently from visible expression similarity
- [ ] live learned-habit capture and promotion demo
- [ ] live context-action-outcome capture for an emergent behavior
- [ ] real Intent Candidate generation from longitudinal robot data
- [ ] explicit human review of a discovered intent candidate
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
- [ ] reproducible statistical evaluation protocol
- [ ] longitudinal uncertainty profile
- [ ] behavior-history portability profile
- [ ] explicit approved-mutation / snapshot profile
- [ ] functional-intent preservation profile
- [ ] model-independent intent-discovery evidence profile
- [ ] explicit intent-candidate approval profile
- [ ] compatibility/certification profile
- [ ] security and privacy profile
- [ ] stable extension mechanism
- [ ] governance model for an open standard

## Non-goals

RCL does not attempt to standardize every robot command, replace ROS 2 or other robot middleware, define consciousness/personhood/subjective motivation, infer causality from association alone, or force physically different embodiments to behave identically. Its scope is the portable representation, translation, history, declared purpose, reviewable purpose hypotheses, and measurable preservation of robot continuity data.
