# Repeated Intent Success v0.1

Observed Intent Success answers a simple question for one controlled execution:

> Did the robot satisfy the declared engineering success condition this time?

Repeated Intent Success asks the next question:

> Does the robot keep satisfying that same WHY across repeated trials and sessions?

## User-level idea

```text
one execution
PASS
→ the goal can be achieved

repeated trials
19 PASS / 1 FAIL
→ how often was the goal observed as satisfied?

multiple sessions
10/10
9/10
10/10
→ does that result remain stable across sessions?
```

This remains purpose-oriented. It does not compare source and target motion.

## Relationship to the existing evaluator

Every repeated trial is first evaluated by the existing Observed Intent Success v0.1 engine.

```text
Repeated series
      ↓
Session
      ↓
Trial
      ↓
Observed Intent Success v0.1
      ↓
pass / fail / not_observable / not_triggered
      ↓
Repeated aggregation
```

That means repeated evaluation reuses the exact same:

- behavior ID matching;
- declared trigger matching;
- declared success-condition matching;
- required / preferred / advisory criticality;
- `pass / fail / not_observable / not_triggered` semantics;
- strategy-as-audit-metadata rule.

The repeated layer does not redefine what one successful trial means.

## Input structure

A Repeated Intent Observation Series contains one observed robot and one or more named sessions.

```text
Series
├─ Session A
│  ├─ Trial 1
│  ├─ Trial 2
│  └─ Trial 3
├─ Session B
│  ├─ Trial 1
│  ├─ Trial 2
│  └─ Trial 3
└─ Session C
   ├─ Trial 1
   ├─ Trial 2
   └─ Trial 3
```

Each trial carries the same `intent_observations` shape already used by single-run Observed Intent Success.

The runtime/public schema is:

```text
intent-observation-series.schema.json
```

## Pooled success rate

For one declared Intent, v0.1 reports:

```text
pass_count
fail_count
not_observable_count
not_triggered_count
missing_observation_count
```

The observed success rate is:

```text
pass / (pass + fail)
```

`not_observable` and `not_triggered` remain visible evidence states, but they are not silently converted into pass or fail observations.

Example:

```text
7 PASS
0 FAIL
1 NOT_OBSERVABLE
1 NOT_TRIGGERED

observed success rate = 7 / 7 = 100%
observable rate       = 7 / 9
```

The report therefore shows both how successful the observable executions were and how much of the series was actually observable.

## Wilson 95% interval

A raw rate such as `19 / 20 = 95%` does not communicate how much statistical uncertainty remains.

v0.1 therefore reports a dependency-light Wilson 95% binomial proportion interval over the pooled pass/fail observations.

```text
19 PASS / 1 FAIL
observed rate = 95%
Wilson 95% ≈ 76.4% .. 99.1%
```

This interval is an uncertainty summary for the observed pass/fail proportion. It is not a universal safety or reliability guarantee.

## Session-level stability

Pooled trials can hide day-to-day or session-to-session variation, so RCL also summarizes each session separately.

For each Intent it reports:

```text
session success rates
mean session success rate
session success-rate standard deviation
Student-t 95% interval when enough sessions exist
```

Sessions are equal-weight units for the session-level summary. A session with more trials does not automatically receive more weight in the session mean.

## Required Intent failures are not averaged away

This is one of the most important rules in v0.1.

```text
99 PASS
1 required FAIL

observed rate = 99%
```

RCL still reports the required failure explicitly and the repeated evaluation is `failed`.

A high average cannot erase a known required failure.

This is not a claim that every application must demand 100% reliability. RCL deliberately does **not** define a universal acceptable success-rate threshold. Application-specific policy may be added outside this v0.1 evidence report.

## Insufficient evidence

By default, a required Intent needs at least three observable pass/fail trials before the repeated report can be treated as an estimate.

```text
2 PASS
0 FAIL

→ no observed failure
→ but insufficient repeated evidence
→ INCONCLUSIVE
```

The threshold is a minimum evidence gate, not a universal quality target.

## Preferred and advisory Intent

A failure in a preferred or advisory Intent remains explicit but nonblocking.

```text
required pre-sit clearance
9 / 9 PASS

preferred handover orientation
8 / 9 PASS

→ repeated evaluation may remain ESTIMATED
→ handover failure is still reported
```

This preserves the existing single-run criticality semantics.

## Strategy remains audit metadata

The source and target may satisfy the same declared purpose with different strategies.

Reference fixtures demonstrate:

```text
V1
source.rearward_body_observation
→ repeated pre-sit Intent success

V2
target.direct_rear_depth_sensing
→ repeated pre-sit Intent success
```

Repeated Intent Success does not reward one strategy for looking more like the source strategy.

## CLI

```bash
rcl evaluate-intent-series \
  examples/intent/sit-assistant-v1 \
  examples/intent-series/sit-assistant-v2.series.json
```

Machine-readable output:

```bash
rcl evaluate-intent-series \
  examples/intent/sit-assistant-v1 \
  examples/intent-series/sit-assistant-v2.series.json \
  --json
```

Write a report:

```bash
rcl evaluate-intent-series \
  examples/intent/sit-assistant-v1 \
  examples/intent-series/sit-assistant-v2.series.json \
  --output repeated-intent-report.json
```

Exit codes:

```text
0  estimated repeated evidence with no required failure/inconclusive gate
7  inconclusive required evidence
8  observed required failure
2  invalid input / validation error
```

## Reference fixtures

```text
examples/intent-series/sit-assistant-v1.series.json
examples/intent-series/sit-assistant-v2.series.json
```

Both contain three sessions with three trials each. They satisfy the same declared Intents using different source-style and target-native strategies.

## What this does not prove

Repeated Intent Success v0.1 does not establish:

- causality;
- consciousness or subjective purpose;
- physical or functional safety certification;
- universal reliability;
- universal acceptance thresholds;
- population-level equivalence of robot models;
- source-motion similarity.

The separation remains:

```text
Capability Path
→ can this body represent a semantic route to the WHY?

Observed Intent Success
→ did one observed execution satisfy the WHY?

Repeated Intent Success
→ how consistently did repeated observed executions satisfy the WHY?

Physical validation
→ is the real system safe and suitable for its application?
```
