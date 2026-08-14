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

Primary goal: make RCL testable against external implementations instead of only the bundled reference adapter.

- [x] ROS 2 reference adapter (Lyrical mobile-base semantic bridge, v0.3-dev)
- [x] adapter conformance test kit (`rcl.adapter.mobile_base.v0.3`)
- [x] machine-readable conformance report schema
- [ ] profile diff command
- [ ] formal capability vocabulary
- [ ] behavior tolerance and evaluation metadata
- [ ] observed-behavior evaluation protocol
- [ ] migration report cross-implementation fixtures
- [ ] extension namespace rules

### v0.3 success criteria

An independently implemented adapter should be able to consume the same semantic fixture, produce a valid migration report, expose capability loss honestly, and pass a shared executable conformance suite.

## v0.4 — private continuity and provenance

Primary goal: support long-lived profiles that may contain user-specific continuity data.

- [ ] memory namespaces
- [ ] encrypted private sections
- [ ] profile signing
- [ ] provenance metadata
- [ ] selective export
- [ ] profile portability rules

## v0.5 — real robot reference migration

Primary goal: replace configuration-only similarity with measured physical behavior continuity.

- [ ] Robot A live behavior capture
- [ ] `.rcl` export
- [ ] Robot B restore
- [ ] measured before/after following behavior
- [ ] measured before/after manipulation behavior
- [ ] observed Continuity Score prototype
- [ ] video demo
- [ ] reproducible test procedure and dataset

## v0.6+ — ecosystem experiments

- [ ] LeRobot integration experiment
- [ ] simulator reference adapters
- [ ] multiple independently maintained robot adapters
- [ ] cross-vendor migration demo
- [ ] version negotiation
- [ ] backward-compatibility policy
- [ ] public adapter registry concept

## v1.0 target — stable continuity interoperability layer

- [ ] stable portable core specification
- [ ] multi-vendor adapter ecosystem
- [ ] independent conformance suites for multiple embodiment classes
- [ ] compatibility/certification profile
- [ ] security and privacy profile
- [ ] stable extension mechanism
- [ ] governance model for an open standard

## Non-goals

RCL does not attempt to standardize every robot command, replace ROS 2 or other robot middleware, define consciousness or personhood, or force physically different embodiments to behave identically. Its scope is the portable representation, translation, and measurable preservation of robot continuity data.
