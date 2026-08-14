# RCL Roadmap

RCL is being developed from a small, testable continuity core toward real multi-robot interoperability. The roadmap is experimental and may change as real robot integrations expose weaknesses in the model.

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

## v0.3 — interoperability and evaluation

Primary goal: make RCL testable against external implementations and begin separating declared continuity from measured continuity.

- [x] ROS 2 reference adapter (Lyrical mobile-base semantic bridge, v0.3-dev)
- [x] adapter conformance test kit (`rcl.adapter.mobile_base.v0.3`)
- [x] machine-readable conformance report schema
- [x] Capability Registry v0.1 with reserved semantic namespaces
- [x] extension capability namespace (`x.<owner>.<semantic_path>`)
- [x] migration-time capability vocabulary validation
- [x] numeric behavior tolerance and evaluation metadata
- [x] observation input format v0.1
- [x] Observed Continuity Evaluation v0.1 (observed-vs-declared)
- [x] machine-readable observed evaluation report schema
- [x] repeated-trial observation format v0.2
- [x] source-vs-target Statistical Continuity Evaluation v0.2
- [x] exact 1D empirical Wasserstein distribution comparison
- [x] repeated-trial minimum sample policy
- [x] Experiment Context / Measurement Protocol v0.1
- [x] strict context gate before statistical scoring
- [x] protocol-selected comparison fields plus informational robot metadata
- [x] Repeated-Session Confidence / Uncertainty v0.1
- [x] equal-weight session aggregation with between-session sample standard deviation
- [x] dependency-free 95% Student-t confidence intervals with a minimum of 3 scorable sessions
- [x] strict cross-session robot/protocol/context series consistency gate
- [x] per-metric session-level similarity uncertainty summaries
- [x] semantic profile diff command and machine-readable diff report
- [x] backward-compatible behavior habit/history metadata
- [x] configured → learning → stable → legacy lifecycle model
- [x] chronological habit-event validation and earlier/later profile fixtures
- [x] Habit Promotion Policy v0.1 with explicit versioned thresholds
- [x] non-mutating configured → learning / learning → stable / stable → legacy review recommendations
- [x] behavior-specific repeated-session evidence gates for stable and legacy review
- [x] machine-readable habit-promotion policy and report schemas
- [x] Explicit Habit Approval / Profile Patch v0.1
- [x] deterministic approval preview with candidate/lifecycle/timestamp preconditions
- [x] immutable new-snapshot apply with regenerated SHA-256 manifest
- [x] approval-history audit event and semantic-parameter immutability check
- [ ] migration report cross-implementation fixtures
- [ ] registry proposal / review workflow

### v0.3 success criteria

An independently implemented adapter should be able to consume the same semantic fixture, use a shared capability vocabulary, produce a valid migration report, expose capability loss honestly, pass a shared executable conformance suite, emit observations that can be evaluated against declared tolerances, participate in repeated-trial source-vs-target behavior comparison under a declared comparable experiment context, report uncertainty across a comparable series of repeated sessions, expose auditable semantic profile evolution without replaying historical events as commands, produce transparent non-mutating habit-promotion review recommendations from versioned evidence gates, and apply an explicitly approved lifecycle transition only into a new validated RCL snapshot without changing semantic behavior parameters.

## v0.4 — private continuity and provenance

Primary goal: support long-lived profiles that may contain user-specific continuity data.

- [ ] memory namespaces
- [ ] encrypted private sections
- [ ] profile signing
- [ ] provenance metadata
- [ ] selective export
- [ ] profile portability rules
- [ ] retained-history compaction / archival policy

## v0.5 — real robot reference migration

Primary goal: replace configuration-only similarity with measured physical behavior continuity across actual source and target robots.

- [ ] Robot A live behavior capture
- [ ] `.rcl` export
- [ ] Robot B restore
- [ ] measured before/after following behavior
- [ ] measured before/after manipulation behavior
- [ ] live learned-habit capture and promotion demo
- [ ] multi-session Statistical Continuity Score on physical robots
- [ ] controlled experiment context capture from real sessions
- [ ] uncertainty and confidence reporting on real robot data
- [ ] user-reviewed habit promotion on real longitudinal evidence
- [ ] explicit approval creating a new real-robot profile snapshot
- [ ] video demo
- [ ] reproducible test procedure and dataset

## v0.6+ — ecosystem experiments

- [ ] LeRobot integration experiment
- [ ] simulator reference adapters
- [ ] multiple independently maintained robot adapters
- [ ] cross-vendor migration demo
- [ ] migration report cross-implementation fixtures
- [ ] registry proposal / review workflow
- [ ] version negotiation
- [ ] backward-compatibility policy
- [ ] public adapter registry concept
- [ ] multi-party capability registry governance experiment

## v1.0 target — stable continuity interoperability layer

- [ ] stable portable core specification
- [ ] stable capability vocabulary and extension policy
- [ ] multi-vendor adapter ecosystem
- [ ] independent conformance suites for multiple embodiment classes
- [ ] measured continuity evaluation profile
- [ ] reproducible statistical evaluation protocol
- [ ] longitudinal uncertainty profile
- [ ] behavior-history portability profile
- [ ] evidence-backed habit-promotion profile
- [ ] explicit approved-mutation / snapshot profile
- [ ] compatibility/certification profile
- [ ] security and privacy profile
- [ ] stable extension mechanism
- [ ] governance model for an open standard

## Non-goals

RCL does not attempt to standardize every robot command, replace ROS 2 or other robot middleware, define consciousness or personhood, or force physically different embodiments to behave identically. Its scope is the portable representation, translation, history, and measurable preservation of robot continuity data.
