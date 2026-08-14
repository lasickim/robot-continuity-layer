# Robot Continuity Layer Specification v0.2

**Status:** Draft / experimental  
**Date:** 2026-08-14

## 1. Purpose

RCL v0.2 extends the portable continuity profile with an explicit **Embodiment Adapter**, a machine-readable **Migration Report**, and the first standardized **Behavior Continuity Score**.

RCL still does not define robot control, consciousness, personhood, or legal identity. It defines a portable technical continuity layer between a robot's accumulated semantic behavior and a replaceable physical body.

> Hardware can be replaced. Experience shouldn't be.

## 2. Continuity domains

The core profile contains `identity.json`, `preferences.json`, `behavior.json`, `skills.json`, and `embodiment.json`. The canonical package extension remains `.rcl`, using a ZIP-compatible container.

## 3. Semantic behavior

Canonical behavior MUST be expressed in an embodiment-independent semantic form wherever practical. Hardware-specific motor limits, joint targets, policy parameters, or vendor configuration may be emitted by an adapter as migration output, but are not canonical continuity identity.

## 4. Required capabilities

A behavior MAY declare `required_capabilities` using semantic capability identifiers. Adapters MAY add stricter capability requirements for a behavior namespace.

## 5. Embodiment Adapter Interface

An RCL v0.2 adapter translates semantic continuity behavior to a target embodiment. The reference Python interface exposes `supports`, `required_capabilities`, `capability_match`, and `translate_behavior`. v0.2 adapters generate a migration plan and are not required to directly actuate hardware.

## 6. Migration statuses

Each behavior migration MUST produce exactly one status: `preserved`, `approximated`, `unsupported`, or `blocked_for_safety`. Unsupported and safety-blocked behaviors use semantic similarity `0.0` in the v0.2 scoring method.

## 7. Preservation policy

Behavior priorities remain `required`, `preferred`, and `optional`. Behavior modes remain `semantic` and `legacy`. Legacy behavior MUST NOT override target safety limits. An unsupported or safety-blocked required behavior MUST report `migration_success: false`, regardless of numerical score.

## 8. Migration Report

The v0.2 report records source robot/profile/embodiment, target embodiment, adapter ID/version, behavior results, capability gaps, mapped target parameters, semantic similarity, Continuity Score, required failures, and safety blocks.

## 9. Behavior Continuity Score v0.2

Priority weights are `required=4`, `preferred=2`, `optional=1`.

```text
Behavior Continuity Score
= 100 × Σ(weight × similarity) / Σ(weight)
```

The scoring method identifier is `rcl.behavior.weighted_similarity.v0.2`. The score measures behavior preservation only and MUST NOT be presented as a measure of consciousness, personhood, identity, emotional authenticity, or legal continuity.

## 10. Reference migration

Robot A has a learned following distance, gentle following speed, cautious turning, a 350 ms stop delay, and a legacy pre-turn observation behavior. Robot B has a different speed envelope and lacks directional attention. The reference adapter preserves following behavior semantically, maps speed style to Robot B's own limits, approximates the legacy observation with a small base-yaw preview, and reports that approximation.

## 11. Safety rule

Safety is outside the Continuity Score optimization target. Implementations MUST NOT increase score by violating target safety limits.

## 12. Privacy and ownership

RCL remains local-first and exportable. v0.2 intentionally excludes raw private audio/video/conversation archives from the reference package.

## 13. Non-goals

Episodic memory transfer, VLA/foundation-model weight migration, universal inverse kinematics, direct hardware safety certification, legal ownership transfer, cloud sync, cryptographic identity, and human-rated emotional continuity are not standardized in v0.2.

## 14. Candidate roadmap

v0.3 targets profile diff, memory namespaces, encrypted private sections, signing/provenance, observed-behavior evaluation, and adapter conformance tests. v1.0 targets a stable portable core, multi-vendor adapter ecosystem, conformance suite, and certification profiles.
