# Observed Continuity Evaluation v0.1

RCL v0.3-dev introduces an experimental **observed-vs-declared** evaluation layer. The goal is to measure whether a target robot actually behaves close enough to a portable semantic behavior profile after migration.

This is deliberately separate from the declared migration score:

```text
Declared semantic profile
        ↓
Migration / adapter
        ↓
Target execution plan
        ↓
Robot B observed behavior
        ↓
Observed Continuity Evaluation
```

## Why a second score exists

A migration report can say that a behavior is representable on Robot B, but that does not prove Robot B executed it closely enough in the real world.

For example, a profile may declare:

```text
preferred following distance = 1.40 m
stop delay                   = 350 ms
```

Robot B might actually produce:

```text
following distance = 1.37 m
stop delay          = 372 ms
```

Observed evaluation decides whether those differences are acceptable under declared tolerances.

## Evaluation metadata

Numeric metrics are attached to an existing behavior and reference an existing semantic parameter instead of duplicating the canonical target value:

```json
{
  "evaluation": {
    "metrics": [
      {
        "metric_id": "following_distance",
        "observable": "following_distance_m",
        "target_parameter": "preferred_distance_m",
        "unit": "m",
        "tolerance": 0.10,
        "zero_credit_at": 0.30,
        "weight": 2.0,
        "required": true
      }
    ]
  }
}
```

`target_parameter` must exist in the same behavior's `parameters` object and must resolve to a numeric value.

## Numeric scoring

For absolute error `e`, tolerance `t`, and zero-credit deviation `z`:

```text
if e <= t:
    similarity = 1.0
elif e >= z:
    similarity = 0.0
else:
    similarity = 1 - ((e - t) / (z - t))
```

`zero_credit_at` must be greater than `tolerance`.

This makes the score intentionally easy to audit:

```text
target = 1.40 m
tolerance = 0.10 m
zero_credit_at = 0.30 m

observed 1.45 m -> similarity 1.00
observed 1.55 m -> similarity 0.75
observed 1.70 m -> similarity 0.00
```

## Weighting

Each metric has its own positive `weight`. The existing behavior preservation priority also contributes:

```text
required  = 4
preferred = 2
optional  = 1

effective metric weight = behavior priority weight × metric weight
```

The overall Observed Continuity Score is the weighted mean of metric similarity values, expressed as a percentage.

## Missing observations

A metric can declare `required: true` or `required: false`.

- Missing required observations are explicit failures, contribute zero similarity, and make `evaluation_success=false`.
- Missing optional observations are reported as `missing_optional` and excluded from the denominator.

A required metric that reaches zero similarity also makes the observed evaluation fail.

## Observation input

Observed data is deliberately separate from the `.rcl` profile:

```json
{
  "observation_version": "0.1",
  "robot_id": "RCL-DEMO-ROVER-B",
  "embodiment_id": "demo-rover-b-v1",
  "captured_at": "2026-08-14T00:30:00Z",
  "behavior_observations": [
    {
      "behavior_id": "navigation.follow_person",
      "metrics": {
        "following_distance_m": 1.37,
        "stop_delay_ms": 372
      }
    }
  ]
}
```

The first observation format only supports numeric metric values. Future versions may add distributions, confidence intervals, trial counts, time-series references, categorical metrics, and source-vs-target statistical comparison.

## CLI

```bash
rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json
```

Reference result:

```text
Observed Continuity Score: 100.00%
Evaluation Success: YES
Status: within_tolerance
Required Failures: 0
- navigation.follow_person.following_distance: within_tolerance (...)
- navigation.follow_person.stop_delay: within_tolerance (...)
```

JSON output:

```bash
rcl evaluate \
  examples/mobile-base \
  examples/observations/demo-rover-b.observations.json \
  --json
```

## Status values

Per metric:

- `within_tolerance`
- `partial`
- `outside_limit`
- `missing`
- `missing_optional`

Overall report:

- `within_tolerance` — all scored metrics received full credit and no required failures occurred.
- `degraded` — some metrics received partial credit but no required metric failed.
- `failed` — a required observation is missing or a required metric reached zero similarity.

## Current limitation

Observed Continuity Evaluation v0.1 compares **Robot B observations to declared semantic targets**. It is not yet a full Robot A observed-distribution vs Robot B observed-distribution equivalence protocol.

That distinction is intentional. The next research step can add repeated trials, distributions, confidence, temporal behavior, and direct source/target empirical comparison without changing the core idea that declared behavior and measured behavior are separate layers.

## Safety and identity boundary

A high observed score is not:

- physical safety certification;
- proof of hardware reliability;
- proof that two robots are physically identical;
- proof of consciousness, personhood, or subjective identity.

It only measures declared numeric behavior metrics under the published experimental scoring rule.
