# Explicit Legacy Expression Optimization / Removal Approval v0.1

RCL preserves a recognizable legacy expression by default. A newer robot body may no longer need that visible gesture for the underlying function, but **functional redundancy is not permission to erase continuity behavior automatically**.

> **Preserve by default. Optimize only by explicit approval.**

This workflow is the mutation boundary for simplifying or removing an active `behavior.expression`.

```text
Declared Intent
  ↓
target-native functional HOW
  ↓
legacy expression still active
  ↓
Expression Optimization Candidate
  ↓
preview
  ↓
explicit approval
  ↓
new immutable snapshot
  ↓
active expression simplified/removed
  +
previous expression retained in expression_history
```

## Why approval is separate from migration

Migration may conclude that a target can satisfy the same functional Intent using a better sensor, controller, or embodiment strategy. That does not imply that a familiar visible expression should disappear immediately.

Example:

```text
V1
rearward glance
  ↓
rear area check

V2 functional HOW
rear depth sensing immediately verifies clearance

V2 continuity expression
rearward glance may still be shown because it is familiar
```

The user or operator may later decide that the visible glance can be simplified or removed. RCL records that as a new reviewed continuity decision rather than silently changing the robot.

## Actions

v0.1 supports two mutation actions:

### `simplify`

Replace the current expression with a complete proposed replacement expression.

The previous expression is copied in full into `behavior.expression_history` before replacement. That snapshot includes any expressive timing metadata, source timing observations, and source hardware-artifact provenance.

### `remove`

Remove the active `behavior.expression` from current continuity behavior.

Removal does **not** delete the previous expression. The exact prior expression remains in `behavior.expression_history`.

`retain` is deliberately not a mutation action. Declining an optimization candidate means the current profile remains unchanged and no no-op snapshot is created.

## Candidate binding

A candidate is bound to the exact current expression using canonical JSON SHA-256.

```json
{
  "candidate_version": "0.1",
  "candidate_id": "expr-remove-2026-001",
  "created_at": "2026-08-15T02:00:00+09:00",
  "behavior_id": "safety.pre_sit_clearance_check",
  "current_expression_sha256": "...",
  "action": "remove",
  "reason": "Target-native rear sensing completes the functional check before the familiar glance.",
  "evidence_refs": ["intent-success://session-42"],
  "replacement_expression": null
}
```

If the active expression changes after this candidate is created, approval is rejected as stale.

A `simplify` candidate contains a complete `replacement_expression`. A byte/semantic-equivalent replacement is rejected as a no-op.

## Preview and apply

Preview never mutates the source profile:

```bash
rcl optimize-expression preview \
  PROFILE \
  candidate.json \
  safety.pre_sit_clearance_check \
  --approved-at 2026-08-15T03:00:00+09:00 \
  --approved-by local-user
```

Apply creates a new immutable-by-default snapshot:

```bash
rcl optimize-expression apply \
  PROFILE \
  candidate.json \
  safety.pre_sit_clearance_check \
  PROFILE_OPTIMIZED \
  --approved-at 2026-08-15T03:00:00+09:00 \
  --approved-by local-user
```

The source snapshot is never overwritten. Existing output paths and output directories inside the source profile are rejected.

## Expression history

Each accepted mutation appends exactly one entry:

```json
{
  "optimization_id": "expr-opt-...",
  "optimized_at": "2026-08-15T03:00:00+09:00",
  "optimized_by": "local-user",
  "action": "remove",
  "candidate_id": "expr-remove-2026-001",
  "candidate_sha256": "...",
  "reason": "...",
  "evidence_refs": ["intent-success://session-42"],
  "from_expression_sha256": "...",
  "to_expression_sha256": "...",
  "expression_snapshot": {
    "expression_id": "observation.brief_rearward_check",
    "preservation_priority": "optional",
    "required_capabilities": ["perception.directional_attention"]
  }
}
```

History is append-only. Apply requires:

```text
after.expression_history
=
before.expression_history + [one approved entry]
```

The previous entries cannot be rewritten as part of optimization.

## Digest chain

For successive optimizations:

```text
Expression v1
  ↓ simplify
Expression v2
  ↓ simplify
Expression v3
  ↓ remove
No active expression
```

history must satisfy:

```text
history[0].to_sha == history[1].from_sha
history[1].to_sha == history[2].from_sha
history[2].to_sha == SHA256(canonical JSON null)
```

RCL defines the terminal no-active-expression digest as SHA-256 of the UTF-8 bytes `null`.

This lets removal remain cryptographically connected to the full earlier expression chain.

## What removal means

After approved removal:

```text
behavior.expression
  absent

behavior.expression_history
  previous gesture snapshots remain
```

This means:

> the robot no longer performs this expression as current continuity behavior,
> but RCL still remembers that the robot used to have it.

History is descriptive and auditable, not executable. A removed expression does not replay itself from history.

## Minimal mutation rule

Expression optimization may change only:

```text
behavior.expression
behavior.expression_history
```

It must not change:

- `behavior.intent`
- semantic behavior parameters
- habit metadata
- source/confidence
- identity
- preferences
- skills
- embodiment

The apply path verifies source payload hashes before and after the operation and validates the output through normal `RCLProfile` validation and Profile Diff.

## Expressive timing is historical continuity too

When an expression contains:

```text
expression.temporal_style
```

that entire block is preserved inside the historical snapshot before simplification/removal. This includes:

- semantic tempo/dwell/transition;
- `naturalize` versus `preserve_style` policy;
- legacy significance;
- non-normative source timing observations;
- source actuator/wiring/controller artifact provenance.

So removing a gesture does not erase how that gesture used to feel.

## Safety boundary

Expression optimization is **not** safety certification.

A candidate may cite Observed Intent Success or other evidence showing that target-native function remains available, but RCL v0.1 does not infer from that evidence that removing the gesture is physically safe in every context.

Safety remains a separate higher-priority constraint.

## Scope boundary

This workflow records an explicit continuity-expression decision. It does not automatically decide that a behavior is obsolete, prove safety, change functional Intent, infer subjective personality, delete historical evidence, or authorize old-history replay.
