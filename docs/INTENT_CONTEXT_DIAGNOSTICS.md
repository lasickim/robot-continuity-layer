# Intent Context Diagnostics v0.1

Intent Discovery can find an association such as:

```text
candidate action present
→ outcome looks better
```

That is useful evidence, but a pooled average can hide an important detail: the apparent effect may depend on a narrower context.

## User-level idea

Suppose the pooled evidence says:

```text
post-release hold
→ object stability improves by +0.18
```

That looks reviewable as an Intent Candidate.

Now split the same evidence by `surface`:

```text
table
→ beneficial effect +0.35

tray
→ beneficial effect +0.02
```

RCL should not silently turn the pooled `+0.18` into a universal story.

Context Diagnostics therefore adds a companion report:

```text
Intent Candidate
→ candidate remains candidate

Context Diagnostic Report
→ CONTEXT_DEPENDENCY_SIGNAL
→ review surface-specific evidence
```

The diagnostic does **not** prove that `surface` caused the difference. It only makes the observed specificity visible.

## Why this is separate from Intent Candidate status

v0.1 deliberately keeps the existing Intent Discovery gates unchanged.

```text
Intent Discovery
→ Is there enough pooled association evidence to review the hypothesis?

Context Diagnostics
→ Does that pooled association look stable across narrower observed contexts?
```

A candidate can therefore be both:

```text
candidate_status = candidate
context status   = context_dependency_signal
```

That means **review with caution**, not automatic rejection.

## What fields are examined

The declared discovery selector remains canonical.

Example:

```json
"context_match": {
  "task": "object_release"
}
```

Within episodes matching that selector, RCL looks for additional context fields that actually vary:

```text
surface
gripper_mode
object_class
location
...
```

Fields already fixed by `context_match` are not re-tested as residual context.

For each varying field value the diagnostic reports:

- episode count;
- action-present count;
- action-absent count;
- action repeat rate;
- action-present outcome mean;
- action-absent outcome mean;
- beneficial effect where estimable;
- effect direction;
- whether enough present/absent observations exist to support that stratum estimate.

## Signals

### `no_material_context_signal`

At least two context values have supported effect estimates and the current v0.1 checks do not find material action-prevalence or effect-direction differences.

Example:

```text
table → beneficial
tray  → beneficial
```

### `context_dependency_signal`

At least one residual context field shows either:

- materially different action prevalence across values; or
- different supported effect classifications across values.

Example:

```text
table → beneficial
tray  → neutral_or_harmful
```

This is a **specificity / possible-confound warning**, not causal identification.

### `insufficient_context_coverage`

A residual context field varies, but fewer than two values have enough action-present and action-absent observations to estimate the effect responsibly.

RCL reports that lack of coverage instead of pretending the pooled result is context-robust.

### `no_residual_context_fields`

The matching evidence does not contain another varying context field to stratify.

This means no context-specificity check was available; it does not prove that no confound exists.

## Current v0.1 thresholds

The diagnostic is deliberately small and dependency-light:

```text
minimum action-present observations per stratum = 2
minimum action-absent observations per stratum  = 2
action repeat-rate spread signal                 = 0.50
```

Effect heterogeneity uses the hypothesis's own `minimum_meaningful_effect` boundary rather than inventing a second universal effect threshold.

These are report-generation rules, not safety thresholds or universal causal criteria.

## Raw evidence

```bash
rcl diagnose-intent-context \
  examples/intent-context/stable-object-release.dataset.json
```

A context-stable reference result reports:

```text
Status: NO_MATERIAL_CONTEXT_SIGNAL
Review Required: NO
Field: surface
```

The context-dependent reference:

```bash
rcl diagnose-intent-context \
  examples/intent-context/context-dependent-object-release.dataset.json
```

reports a review warning while leaving the underlying Intent Candidate status separate.

Machine-readable output:

```bash
rcl diagnose-intent-context DATASET --json
rcl diagnose-intent-context DATASET --output context-report.json
```

The command returns exit code `7` when context review is required and `0` when no diagnostic review signal is present. Invalid input returns `2` through the main `rcl` router.

## Aggregate evidence

Context Diagnostics also works on action-stratified Experience Summaries:

```bash
rcl diagnose-intent-context-summary \
  experience-summary.json \
  intent-summary-hypothesis.json
```

Aggregate mode consumes only the counts and outcome statistics retained by Experience Compaction.

It does **not** reconstruct pseudo-episodes.

Equivalent raw and compacted evidence are regression-tested to produce equivalent context diagnostics.

## What the report does not claim

Context Diagnostics does not:

- prove a context field is a confounder;
- prove causality;
- perform interventions or counterfactual inference;
- fit propensity models;
- automatically reject an Intent Candidate;
- automatically approve an Intent Candidate;
- mutate an RCL profile;
- certify physical or functional safety;
- infer subjective motivation.

Every report keeps:

```text
causal_claim = false
```

## Reference fixtures

```text
examples/intent-context/stable-object-release.dataset.json
examples/intent-context/context-dependent-object-release.dataset.json
```

The first demonstrates context-stable evidence. The second demonstrates a pooled candidate whose observed effect differs materially across `surface` values.
