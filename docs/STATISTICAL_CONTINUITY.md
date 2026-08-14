# RCL Statistical Continuity Evaluation v0.2

RCL Statistical Continuity Evaluation compares repeated observations from a source robot and a target robot for the same declared semantic behavior metric.

It extends the v0.1 observed-vs-declared evaluator:

```text
v0.1
Declared semantic target
        ↓
Single Robot B observation
        ↓
Observed Continuity Score

v0.2
Robot A repeated trials
        ↓
Empirical distribution
        ↘
          Distribution comparison
        ↗
Robot B repeated trials
        ↓
Statistical Continuity Score
```

The goal is to detect continuity loss that a single measurement or mean-only comparison can miss.

## Why distributions matter

Two robots can have the same average behavior and still feel observably different.

For example:

```text
Robot A distances: 1.40, 1.40, 1.40, 1.40, 1.40
Robot B distances: 1.20, 1.20, 1.40, 1.60, 1.60

mean(A) = 1.40 m
mean(B) = 1.40 m
```

A mean-only test would call them identical. Their behavioral spread is clearly different.

RCL v0.2 therefore compares the full one-dimensional empirical sample distributions.

## Repeated-trial input

Source and target captures use the same schema but remain separate files:

```json
{
  "trial_observation_version": "0.1",
  "robot_id": "RCL-DEMO-ROVER-A",
  "embodiment_id": "demo-rover-a-v1",
  "captured_at": "2026-08-14T03:10:00Z",
  "behavior_trials": [
    {
      "behavior_id": "navigation.follow_person",
      "metrics": {
        "following_distance_m": [1.34, 1.36, 1.37, 1.38, 1.40],
        "stop_delay_ms": [320, 330, 340, 350, 360]
      }
    }
  ]
}
```

The portable `.rcl` profile does not store raw repeated measurements. It only declares the semantic metric and evaluation policy.

## Metric policy

The same evaluation metadata used by the v0.1 observed evaluator is reused:

```json
{
  "metric_id": "following_distance",
  "observable": "following_distance_m",
  "target_parameter": "preferred_distance_m",
  "unit": "m",
  "tolerance": 0.10,
  "zero_credit_at": 0.30,
  "weight": 2.0,
  "required": true,
  "min_trials": 5
}
```

`min_trials` is optional and defaults to 5 for repeated-trial evaluation. It must be at least 2.

## Distribution distance

The v0.2 method uses exact one-dimensional Wasserstein-1 distance between the empirical source and target samples.

Method identifier:

```text
rcl.observed.empirical_wasserstein.v0.2
```

In one dimension, Wasserstein-1 distance is the area between the two empirical cumulative distribution functions.

A useful property for RCL is that the result remains in the metric's original unit:

```text
following distance → meters
stop delay         → milliseconds
```

That lets the existing tolerance policy remain human-readable.

## Similarity rule

For Wasserstein distance `d`, tolerance `t`, and zero-credit threshold `z`:

```text
d <= t      → similarity 1.0
t < d < z   → linear falloff from 1.0 to 0.0
d >= z      → similarity 0.0
```

Example:

```text
tolerance      = 0.10 m
zero_credit_at = 0.30 m
W1 distance    = 0.16 m

similarity = 1 - ((0.16 - 0.10) / (0.30 - 0.10))
           = 0.70
```

## Overall score

Each scored metric uses:

```text
effective weight
= behavior preservation-priority weight × metric weight
```

Priority weights remain:

```text
required  = 4
preferred = 2
optional  = 1
```

Overall score:

```text
100 × Σ(effective_weight × similarity) / Σ(effective_weight)
```

A required metric with zero similarity, missing data, or insufficient trials forces `evaluation_success=false`.

Missing or insufficient optional metrics remain visible in the report but do not silently receive credit and do not enter the denominator.

## Reported descriptive statistics

The report includes, for each scored metric:

- source sample count;
- target sample count;
- source mean;
- target mean;
- source sample standard deviation;
- target sample standard deviation;
- exact Wasserstein-1 distance;
- similarity;
- status.

Means and standard deviations are explanatory diagnostics. The v0.2 similarity is based on the empirical distribution distance, not a weighted sum of separate mean and variance tests.

## Status values

For scored metrics:

```text
distribution_within_tolerance
distribution_partial
distribution_outside_limit
```

For unavailable data:

```text
missing_both
missing_source
missing_target
insufficient_both
insufficient_source
insufficient_target
```

Overall status:

```text
matched   score = 100 and no required failure
degraded  score < 100 and no required failure
failed    required metric failure exists
```

## CLI

Run the bundled reference comparison:

```bash
rcl compare-trials \
  examples/mobile-base \
  examples/trials/demo-rover-a.trials.json \
  examples/trials/demo-rover-b.trials.json
```

JSON output:

```bash
rcl compare-trials \
  examples/mobile-base \
  examples/trials/demo-rover-a.trials.json \
  examples/trials/demo-rover-b.trials.json \
  --json
```

Write a report:

```bash
rcl compare-trials \
  examples/mobile-base \
  robot-a.trials.json \
  robot-b.trials.json \
  --output statistical-continuity.report.json
```

## Interpretation boundary

A high score means the measured source and target empirical distributions were close under the declared metric policy.

It does **not** prove:

- that the two robots are statistically identical in every behavioral dimension;
- that the sample size is sufficient for a formal scientific equivalence claim;
- that trials were independent or identically distributed;
- that the environment and measurement system were perfectly controlled;
- physical safety certification;
- consciousness, personhood, or subjective identity continuity.

Future RCL work can add experimental design metadata, confidence intervals, repeated-session analysis, and source/target capture protocols without changing the basic distinction between semantic continuity and measured continuity.
