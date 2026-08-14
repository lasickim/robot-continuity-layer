# Habit Promotion Policy v0.1

RCL Habit Promotion Policy turns declared habit history plus repeated-session reproducibility evidence into a **review recommendation** for the next lifecycle state.

It does not mutate the profile.

```text
configured
    ↓ review candidate
learning
    ↓ review candidate
stable
    ↓ review candidate
legacy
```

## Why this is separate from habit history

Habit history records what has already been declared about a behavior over time. Promotion policy asks a different question:

> Is the available evidence strong enough that a human or higher-level policy should review a lifecycle transition?

The output is therefore advisory.

```text
profile + history + evidence
             ↓
     promotion policy
             ↓
  candidate / blocked
             ↓
       explicit review
             ↓
 optional future profile update
```

The evaluator never performs the final profile update.

## Evidence boundary

The current repeated-session report measures Robot A ↔ Robot B continuity under controlled repeated sessions. That report is **supporting reproducibility evidence**. It is not direct proof that a habit originally formed or stabilized inside Robot A.

Habit formation evidence remains in the profile itself:

- first-observed time;
- history event sequence;
- lifecycle timestamps;
- behavior confidence;
- optional user confirmation.

Stable and legacy review combine those history facts with repeated-session evidence so a high cross-robot continuity score cannot act as the only reason for promotion.

## Published default policy

The default policy is stored in:

```text
rcl/data/habit-promotion-policy-v0.1.json
spec/policies/habit-promotion-policy-v0.1.json
```

The thresholds are deliberately explicit and versioned. They are not universal truths.

### configured → learning

Default gates:

```text
observation age       >= 14 days
history events        >= 2
behavior confidence   >= 0.50
```

Repeated-session evidence is not mandatory for this first transition.

### learning → stable

History gates:

```text
source                = learned
observation age       >= 30 days
history events        >= 2
behavior confidence   >= 0.80
```

Repeated-session supporting gates:

```text
report status               = estimated
evaluation success          = true
scorable sessions           >= 3
mean continuity score       >= 90
between-session std         <= 5
95% score CI half-width     <= 5
qualifying behavior metrics >= 1
metric mean similarity      >= 0.90
metric 95% CI half-width    <= 0.10
```

The behavior-specific metric gate is important. A high overall continuity score cannot promote `navigation.follow_person` if that behavior's own metrics are unstable.

### stable → legacy

The default legacy review is intentionally stricter:

```text
stable age             >= 180 days
history events         >= 3
behavior confidence    >= 0.80
user confirmation      required
scorable sessions      >= 5
```

The same continuity-quality and behavior-metric gates used for stable review also apply.

## CLI

Run the bundled learning-profile example:

```bash
rcl habit-candidates \
  examples/history/mobile-base-before \
  examples/policy/demo-follow-person.session-report.json
```

JSON output:

```bash
rcl habit-candidates \
  examples/history/mobile-base-before \
  examples/policy/demo-follow-person.session-report.json \
  --json
```

Use a custom policy:

```bash
rcl habit-candidates \
  my-profile \
  session-report.json \
  --policy my-promotion-policy.json
```

Evaluate at an explicit point in time:

```bash
rcl habit-candidates \
  my-profile \
  session-report.json \
  --as-of 2027-02-01T00:00:00Z
```

`--as-of` changes age-related gates only. It does not rewrite history.

## Example result

```text
RCL Habit Promotion Review
Policy: rcl.habit.promotion.default.v0.1@0.1
Decisions: candidates=1 blocked=0 terminal=0

- navigation.follow_person: learning -> stable [CANDIDATE]
```

A blocked result exposes every failed gate rather than returning only a boolean.

```text
- navigation.follow_person: learning -> stable [BLOCKED]
    BLOCK scorable_sessions: actual=2 required={'minimum': 3}
    BLOCK score_ci_half_width: actual=None required={'maximum': 5.0}
```

## Non-mutating contract

Calling the policy evaluator must not change:

- `behavior.parameters`;
- `behavior.source`;
- `behavior.confidence`;
- `habit.lifecycle`;
- lifecycle timestamps;
- history events.

A future explicit approval/write operation may apply a reviewed transition. That operation is intentionally outside v0.1.

## Safety boundary

Habit promotion never outranks target safety constraints. A `legacy` recommendation does not make an unsafe behavior executable or exempt it from migration/conformance checks.

## What a candidate does not mean

A candidate does not prove:

- consciousness;
- personhood;
- emotional authenticity;
- robot identity;
- user consent;
- physical safety;
- autonomous learning success.

It means only that the declared evidence satisfies the selected, versioned engineering review policy.
