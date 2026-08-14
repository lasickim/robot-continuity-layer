# Expression Optimization Recommendation Policy v0.1

RCL preserves familiar expression by default. A target robot may later have enough functional evidence to justify **reviewing** whether a legacy expression should be simplified or removed, but recommendation and mutation remain separate operations.

> **Recommend automatically. Change only by explicit approval.**

A second boundary is equally important:

> **A target limitation is not permission to forget.**

If one embodiment cannot reproduce an old gesture, RCL does not treat that incompatibility as evidence that the gesture should disappear from continuity data.

## Pipeline

```text
Current RCL profile
  ├─ declared Intent
  └─ active legacy expression
        ↓
Migration report
  ├─ target-native Intent strategy
  └─ expression representability
        +
Observed Intent Success report
  ├─ declared success condition result
  └─ observed strategy ID
        ↓
Expression Optimization Recommendation Policy
        ↓
review_removal
review_simplification
retain
inconclusive
        ↓
human review
        ↓
optional explicit Expression Optimization Candidate
        ↓
rcl optimize-expression preview / apply
```

The recommendation evaluator never changes the profile and never calls the optimization approval workflow automatically.

## Evidence boundary

v0.1 requires the machine-readable evidence to agree before an expression can be recommended for optimization review.

For a behavior with a declared Intent, the evaluator checks:

1. the migration source robot/embodiment matches the current profile;
2. the Observed Intent Success declared profile matches the current profile;
3. the migration target embodiment matches the observed target embodiment;
4. the current expression ID matches the migration expression result;
5. the current goal/trigger/success condition matches the migration and observed reports;
6. Intent migration status is `preserved`;
7. Observed Intent Success status is `pass`;
8. a target-native strategy is declared;
9. by default, the observed strategy ID exactly matches the migration target strategy;
10. no relevant behavior/Intent/expression/timing result is `blocked_for_safety`;
11. the expression is representable on this target before optimization review is suggested.

If reports disagree on identity, target embodiment, goal semantics, expression identity, or other exact referents, validation fails rather than guessing.

## Why `redundancy_proven=false`

Observed Intent Success shows that the declared engineering success condition was observed as satisfied. It does **not** by itself establish a causal counterfactual such as:

> “The same outcome would definitely have occurred if the legacy expression had not happened.”

Migration also shows that a target-native strategy can represent the Intent, but that is representability evidence, not causal proof about the old gesture.

Therefore every v0.1 report and every recommendation carries:

```text
redundancy_proven = false
non_mutating = true
```

A `review_removal` decision means:

> “The available engineering evidence is strong enough to review removal.”

It does **not** mean:

> “RCL proved this gesture is useless and safe to delete.”

## Default policy

The published default policy is:

```text
spec/policies/expression-optimization-recommendation-policy-v0.1.json
```

Its conservative decision matrix is:

| Expression priority | Legacy significance | Default decision |
|---|---|---|
| optional | incidental | `review_removal` |
| optional | recognized | `review_simplification` |
| optional | user_valued | `retain` |
| optional | unspecified | `review_simplification` |
| preferred | incidental | `review_simplification` |
| preferred | recognized | `review_simplification` |
| preferred | user_valued | `retain` |
| preferred | unspecified | `review_simplification` |

These are versioned review defaults, not universal truths about what users value.

### Why unspecified does not default to removal

An expression with no declared temporal-style significance is not automatically disposable. Missing significance metadata may simply mean the system has not learned or recorded whether users value the behavior.

Therefore `optional + unspecified` defaults to `review_simplification`, not `review_removal`.

### Why user-valued defaults to retain

`legacy_significance=user_valued` is direct continuity metadata saying the manner itself matters. The recommendation layer therefore keeps it by default. A user can still explicitly choose to change it later through the approval workflow.

## Target inability is not forgetting

Consider a wrist-roll expression that Robot V1 could perform, but Robot V2 lacks the required wrist-roll capability.

```text
Functional Intent: preserved
Observed Intent Success: pass
Expression on V2: unsupported
```

The recommendation is:

```text
retain
```

not `review_removal`.

The target's inability to reproduce the expression is an embodiment compatibility fact. It is not evidence that continuity should erase the expression from the profile.

A future embodiment may support it again.

## Safety boundary

If the migration evidence contains `blocked_for_safety` for relevant behavior, Intent, expression, or expression timing, the default recommendation is `retain` rather than trying to optimize around the safety condition.

Expression Recommendation is not a safety evaluator and cannot authorize bypassing target safety controls.

## Decisions

### `review_removal`

The expression is representable, optional, incidental, and the target-native functional strategy has matching successful observed evidence. Review whether an explicit `remove` candidate should be created.

```text
suggested_action = remove
recommended_next_action = review_remove_candidate
```

No candidate is created automatically.

### `review_simplification`

Functional evidence supports review, but continuity significance makes outright removal too aggressive under the default policy.

```text
suggested_action = simplify
recommended_next_action = design_replacement_then_review
```

Core v0.1 never invents a replacement gesture. A human, designer, planner, or future model-neutral proposer may design one, which must then go through explicit approval.

### `retain`

Current evidence or continuity significance favors keeping the expression active. Examples include:

- `user_valued` expression;
- target cannot reproduce the expression;
- Observed Intent Success is not `pass`;
- Intent migration is not preserved;
- safety block is present.

### `inconclusive`

The relevant evidence is missing or not directly comparable. Examples include:

- target strategy missing;
- observed strategy does not match the declared target strategy when exact matching is required;
- behavior has an active expression but no declared Intent.

## Deterministic provenance

Recommendation IDs are deterministic over the evidence identity:

```text
behavior_id
+ current expression SHA-256
+ target embodiment ID
+ migration report SHA-256
+ Intent Success report SHA-256
+ policy SHA-256
```

The report creation timestamp is not part of recommendation identity.

This means the same profile, target evidence, and policy produce the same recommendation IDs even if the report is rendered later.

## CLI

```bash
rcl expression-recommendations \
  PROFILE \
  migration-report.json \
  intent-success-report.json
```

JSON:

```bash
rcl expression-recommendations \
  PROFILE \
  migration-report.json \
  intent-success-report.json \
  --json
```

Write a machine-readable report:

```bash
rcl expression-recommendations \
  PROFILE \
  migration-report.json \
  intent-success-report.json \
  --output expression-recommendations.json
```

Custom versioned policy:

```bash
rcl expression-recommendations \
  PROFILE \
  migration-report.json \
  intent-success-report.json \
  --policy custom-policy.json
```

## Relationship to explicit optimization approval

Recommendation does not replace the already-defined approval boundary.

```text
Recommendation Report
        ↓
review
        ↓
optional Expression Optimization Candidate
        ↓
rcl optimize-expression preview
        ↓
explicit approval
        ↓
rcl optimize-expression apply
        ↓
new immutable snapshot
```

The candidate still binds to the exact current expression SHA-256, and accepted simplify/remove operations still preserve the previous complete expression in append-only `expression_history`.

## Non-goals

Expression Optimization Recommendation v0.1 does not:

- mutate the profile;
- automatically create or approve a remove/simplify candidate;
- prove causal redundancy;
- infer that the user dislikes an expression;
- infer that an unsupported target expression should be forgotten;
- invent a replacement expression;
- replay historical expressions;
- certify physical safety;
- override target safety constraints;
- define one universal rule for what counts as robot personality or attachment.

It is a deterministic, versioned **review recommendation layer** between functional evidence and explicit continuity mutation.
