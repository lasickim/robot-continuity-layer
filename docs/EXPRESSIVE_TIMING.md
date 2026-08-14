# Expressive Timing / Motion Style v0.1

RCL separates **what a robot needs to accomplish** from **how a familiar visible gesture feels over time**.

The core principle is:

> **Preserve the gesture, not the limitation.**

A source robot may have looked behind slowly because of motor torque, gearing, wiring, power, or controller latency. A future robot should not automatically inherit those physical limitations as if they were part of the intended behavior.

At the same time, tempo can become part of a recognizable habit. If a slow, careful glance became a user-valued mannerism, RCL should be able to preserve that temporal character explicitly.

## Separation of concerns

```text
WHY
Declared Intent
"verify the sitting area is clear"

FUNCTIONAL HOW
V2-native sensing / control
"direct rear depth sensing"

LOOKS
Legacy expression
"brief rearward glance"

FEELS OVER TIME
Expressive temporal style
"natural turn → brief dwell → smooth return"
```

The functional check may complete before the visible expression. RCL never requires a legacy expression to delay or weaken a required safety decision.

## Portable temporal style

Optional metadata lives under `behavior.expression.temporal_style`:

```json
{
  "tempo": "natural",
  "dwell": "brief",
  "transition": "smooth",
  "timing_policy": "naturalize",
  "legacy_significance": "recognized",
  "source_timing_observation": {
    "motion_duration_ms": 1400,
    "dwell_duration_ms": 220,
    "return_duration_ms": 1350,
    "normative": false
  },
  "source_artifacts": [
    {
      "artifact": "actuator_speed_limit",
      "effect": "slower_than_intended"
    },
    {
      "artifact": "wiring_constraint",
      "effect": "slower_than_intended"
    }
  ]
}
```

### Tempo

```text
deliberate
relaxed
natural
quick
```

These are portable semantic classes, not universal millisecond values. Each target adapter or embodiment may map the same semantic class to different safe concrete timing.

### Dwell

```text
none
brief
natural
held
```

### Transition

```text
gentle
smooth
direct
crisp
```

This describes the recognizable character of entering/leaving the expression. It is not a joint trajectory or acceleration command.

## `naturalize` versus `preserve_style`

### `naturalize`

Use when the source timing was affected by hardware limitations or when the portable gesture should be reproduced at a natural target-native tempo.

Reference example:

```text
V1 observed turn: 1400 ms
Reason: actuator + wiring limitation
Portable tempo: natural

V2 target profile:
natural turn = 380 ms
brief dwell = 160 ms
natural return = 360 ms

Result:
status = naturalized
```

The 1400 ms source observation remains provenance only.

### `preserve_style`

Use when the temporal style itself has become a recognized or user-valued continuity feature.

```text
Portable tempo: deliberate
Legacy significance: user_valued
Timing policy: preserve_style

V2 target deliberate turn: 900 ms
Result: preserved
```

`preserve_style` is invalid when `legacy_significance=incidental`. An incidental source delay cannot silently become a normative legacy trait.

## Source timing observations are never commands

`source_timing_observation` is optional audit evidence.

It must always contain:

```json
{
  "normative": false
}
```

This makes the distinction explicit:

```text
Observed historically ≠ required on the target
```

Raw source duration is therefore never copied simply because it was measured.

## Target-native timing realization

Portable RCL data does not contain motor commands or canonical joint trajectories.

A target adapter may provide a timing profile such as:

```json
{
  "tempo_duration_ms": {
    "deliberate": 900,
    "relaxed": 620,
    "natural": 380,
    "quick": 260
  },
  "dwell_duration_ms": {
    "none": 0,
    "brief": 160,
    "natural": 320,
    "held": 700
  },
  "min_safe_motion_duration_ms": 220,
  "max_safe_motion_duration_ms": 1200
}
```

`realize_temporal_style()` resolves semantic style against that target-native profile.

The resulting millisecond plan belongs to the migration/execution plan, not the portable legacy definition.

## Safety bounds

If a requested semantic timing maps outside target safety limits, the target may clamp it and report:

```text
status = approximated
```

Example:

```text
requested quick target timing = 120 ms
minimum safe timing = 220 ms

realized = 220 ms
status = approximated
```

A target may also explicitly return:

```text
blocked_for_safety
```

for an expressive timing plan it must not execute.

A timing block does not erase a preserved functional Intent. The target should keep the safe functional strategy and omit or safely replace the legacy expression.

## Migration facets remain separate

A normal V2 result may be:

```text
Behavior:          preserved
Intent:            preserved
Functional HOW:    direct_rear_clearance_sensing
Expression:        preserved
Expression Timing: naturalized
```

This means the new body is fully used while the familiar manner remains visible.

Another target may report:

```text
Behavior:          preserved
Intent:            preserved
Expression:        unsupported
Expression Timing: unsupported
```

The functional goal still survives.

## Reference fixtures

```text
examples/expression-timing/naturalized-rearward-glance.json
examples/expression-timing/deliberate-rearward-glance.json
examples/targets/intent-demo-v2-expressive.embodiment.json
```

The first demonstrates hardware-limited V1 timing becoming faster and natural on V2. The second demonstrates intentionally preserved slow/deliberate tempo because the timing itself is user-valued.

## Non-goals

Expressive Timing v0.1 does not:

- standardize joint trajectories;
- define one universal human-like speed;
- require maximum target motor speed;
- turn historical hardware defects into identity requirements;
- claim that a timing style proves personality or subjective emotion;
- override target safety limits;
- automatically approve removal of a legacy expression.

It is portable engineering metadata for the temporal character of recognizable robot behavior.
