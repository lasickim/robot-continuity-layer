# Summary-aware Habit Evidence v0.1

RCL can now evaluate repeated semantic behavior evidence from either **raw Experience episodes** or a **compacted Experience Summary**.

The core rule is simple:

> **Aggregate evidence may support Habit review, but it must never pretend to be raw experience.**

## Why this exists

A long-lived robot may accumulate many years of Experience episodes.

RCL already supports:

```text
raw Experience
      ↓
Compaction
      ↓
long-lived Summary
      ↓
Retention / Archive / Prune lifecycle
```

After that lifecycle, every old raw episode may not remain in the active store forever. Habit analysis therefore needs to understand compacted evidence without inventing fake observations.

## Raw vs aggregate

Raw mode means the evaluator can directly inspect the source episodes.

```text
evidence_basis = raw
source_verification = direct_source
```

Aggregate mode means the evaluator reads stored semantic group counts and time ranges from an Experience Summary.

```text
evidence_basis = aggregate
pseudo_episodes_created = false
```

If the original Experience Store is also available, RCL can verify the Summary against that exact raw source:

```text
source_verification = raw_verified
```

If the raw source is no longer available, the report remains honest:

```text
source_verification = summary_declared
```

That means the aggregate report relies on the provenance declared by the stored Summary. It does not claim that raw bytes were re-verified.

## Comparable metrics

Raw and aggregate evaluators expose the same review metrics:

- matched semantic-group count;
- episode count;
- action-present count;
- action-absent count;
- repeat rate;
- first observed time;
- last observed time;
- observation span in days;
- per-group repeat-rate summaries.

For equivalent evidence, those metrics should match.

Example:

```text
navigation.follow_person

RAW
episodes=10
present=8
repeat_rate=0.80
span=30 days

AGGREGATE
episodes=10
present=8
repeat_rate=0.80
span=30 days
```

The numbers may match while the provenance remains different.

## Reference policy

The bundled v0.1 policy is deliberately conservative:

```text
matched episodes        >= 8
action present          >= 5
repeat rate             >= 0.60
observation span        >= 14 days
matched semantic groups >= 1
```

These thresholds are reference engineering defaults, not a universal definition of a habit.

A report is either:

```text
sufficient
insufficient
```

`SUFFICIENT` means only that the repeated semantic action evidence is substantial enough to support Habit review under this policy.

It does **not** mean the behavior is automatically `stable` or `legacy`.

## Context selectors

A deployment may evaluate the same action in a narrower semantic context.

For example:

```text
all person-following evidence
→ 10 episodes
→ sufficient

zone=home only
→ 5 episodes
→ insufficient under the default policy
```

This prevents a broad pooled history from silently answering a narrower Habit question.

## Habit Promotion integration

Existing Habit Promotion remains unchanged by default.

```python
evaluate_habit_promotion_candidates(...)
```

continues to use its existing history and repeated-session semantics.

Deployments that want additional formation evidence may opt in:

```python
from rcl.habit_evidence_promotion import (
    evaluate_habit_promotion_with_formation_evidence,
)

report = evaluate_habit_promotion_with_formation_evidence(
    profile,
    session_report,
    formation_evidence_reports=[habit_evidence_report],
)
```

A matching Habit Evidence Report adds an additional gate.

```text
sufficient   → gate passes
insufficient → gate blocks review
```

The helper never creates `habit.events`, never rewrites lifecycle timestamps, and never converts aggregate groups into synthetic history.

## CLI

Raw evidence:

```bash
rcl evaluate-habit-evidence \
  examples/experience/habit-follow-person.episodes.json \
  navigation.follow_person
```

Aggregate evidence:

```bash
rcl evaluate-habit-evidence-summary \
  summary.json \
  navigation.follow_person
```

If raw evidence is still available:

```bash
rcl evaluate-habit-evidence-summary \
  summary.json \
  navigation.follow_person \
  --source-store examples/experience/habit-follow-person.episodes.json
```

A narrower context can be selected with JSON:

```bash
--context-json '{"zone":"home"}'
```

The human-readable CLI always states the evidence basis, source-verification level, and that no pseudo-episodes or lifecycle mutation occurred.

## Relationship to retention

Retention and Habit Evidence answer different questions.

```text
Retention
→ may this raw evidence move through retain/archive/prune review?

Habit Evidence
→ what repeated semantic behavior evidence remains available for review?
```

A `prune_candidate` decision does not itself create better Habit evidence, and a sufficient aggregate Habit report does not authorize pruning.

## Scope boundary

Habit Evidence v0.1 does not:

- infer subjective habit;
- prove causality;
- reconstruct deleted episodes;
- create synthetic history events;
- automatically promote lifecycle state;
- mutate an RCL profile;
- replace repeated-session continuity evidence;
- certify physical safety.

It is an explicit evidence/provenance layer for long-lived Habit review.
