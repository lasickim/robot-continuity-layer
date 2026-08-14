# Robot Continuity Layer Specification v0.1

**Status:** Draft / experimental  
**Date:** 2026-08-14

## 1. Purpose

Robot Continuity Layer (RCL) defines a portable representation for robot continuity across repair, replacement, upgrade, and embodiment change.

RCL does **not** define robot control itself. It defines the information that should survive when control hardware changes.

The central question is:

> Which properties belong to the current body, and which properties belong to the continuing robot experience?

## 2. Continuity model

RCL v0.1 separates five domains.

### 2.1 Identity
Stable identifiers and lineage metadata for the continuity profile. Identity is not legal personhood and does not imply consciousness. It is a technical continuity identifier.

### 2.2 Preferences
Learned or configured tendencies that are not themselves executable motions, such as preferred following distance, quiet-hours motion preference, preferred side when accompanying a user, or task ordering preference.

### 2.3 Behavior
Semantic, observable behavioral tendencies. Behavior SHOULD be represented semantically. Raw motor values, actuator PWM, joint trajectories, GPIO values, and vendor-specific command packets MUST NOT be used as the canonical continuity representation.

### 2.4 Skills
A record of capabilities and accumulated experience with those capabilities. RCL v0.1 does not prescribe how a skill is implemented.

### 2.5 Embodiment
A description of the current body's relevant capabilities and constraints.

## 3. Canonical package

An RCL v0.1 package MUST contain `manifest.json`, `identity.json`, `preferences.json`, `behavior.json`, `skills.json`, and `embodiment.json`. The canonical file extension is `.rcl`, using a ZIP-compatible archive.

## 4. Manifest

`manifest.json` identifies the package and protects payload integrity with SHA-256 digests. Digital signatures are deferred to a later version.

## 5. Semantic behavior requirement

A continuity behavior SHOULD answer: **What observable tendency should remain recognizable after migration?** It SHOULD NOT answer which exact actuator commands should be replayed.

## 6. Preservation policy

Each behavior can declare `required`, `preferred`, or `optional` preservation priority and `semantic` or `legacy` mode. Legacy preservation MUST never override safety limits of the target embodiment.

## 7. Embodiment adapters

An adapter translates RCL semantic behavior to a target robot body and SHOULD report one status per behavior: `preserved`, `approximated`, `unsupported`, or `blocked_for_safety`.

## 8. Continuity score

RCL v0.1 reserves the concept of a Continuity Score but does not standardize the formula. A score MUST NOT hide unsupported or safety-blocked behavior.

## 9. Privacy and ownership principles

RCL v0.1 is local-first. Implementations SHOULD allow full profile export, avoid mandatory vendor cloud dependency, separate private memories from public behavior metadata, make deletion possible, and avoid treating user-generated robot history as a transferable corporate asset by default.

## 10. Compatibility

A conforming v0.1 reader MUST reject a package whose major RCL version it does not support.

## 11. First reference experiment

The first reference experiment migrates a mobile robot's preferred following distance, speed style, turning style, and stop delay from Robot A to Robot B without copying raw motor commands.

## 12. Non-goals for v0.1

Consciousness or personhood claims, unrestricted memory transfer, raw model-weight migration, universal inverse kinematics, universal skill execution, legal ownership standards, and cloud business models are out of scope.
