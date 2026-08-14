# Behavior Habit History v0.1

RCL behavior history records how a semantic behavior became established over time without turning historical events into executable commands.

## Two separate axes

`source` answers **where the behavior came from**:

```text
configured
learned
imported
```

`habit.lifecycle` answers **how established the behavior is**:

```text
configured → learning → stable → legacy
```

These axes are intentionally independent. A behavior can remain `source: learned` while its lifecycle advances from `learning` to `stable` or `legacy`.

## Example

```json
{
  "behavior_id": "navigation.follow_person",
  "parameters": {
    "preferred_distance_m": 1.32,
    "stop_delay_ms": 420
  },
  "source": "learned",
  "habit": {
    "lifecycle": "stable",
    "first_observed_at": "2026-01-15T00:00:00Z",
    "stable_since": "2026-07-01T00:00:00Z",
    "user_confirmed_at": "2026-07-15T00:00:00Z",
    "events": [
      {
        "event_id": "follow-003",
        "observed_at": "2026-07-01T00:00:00Z",
        "event_type": "stabilized",
        "parameter_values": {
          "preferred_distance_m": 1.32,
          "stop_delay_ms": 420
        },
        "evidence_ref": "sessions/person-following-2026H1"
      }
    ]
  }
}
```

## Lifecycle meanings

- **configured** — intentionally introduced behavior that has not yet become a learned habit.
- **learning** — repeated experience is still changing or refining the behavior.
- **stable** — the behavior has remained sufficiently consistent to be treated as an established habit.
- **legacy** — a long-lived recognizable behavior that the continuity profile explicitly wants to preserve when safe and physically representable.

`legacy` never overrides target safety constraints.

## Event types

v0.1 defines:

```text
configured
observed
learned_update
stabilized
legacy_promoted
user_confirmed
note
```

Events may include a partial `parameter_values` snapshot, a note, or an external `evidence_ref`.

The event log is **descriptive**. The current executable semantic values remain in the behavior's top-level `parameters` object. Loading history never replays events and never mutates current behavior.

## Validation

RCL validates that:

- stable/legacy lifecycles have the required timestamps;
- `stable_since` does not precede `first_observed_at`;
- `legacy_since` does not precede the stable history;
- user confirmation does not predate first observation;
- event IDs are unique within a behavior;
- event timestamps are chronological and do not predate first observation.

## Profile diff

Two snapshots can be compared with:

```bash
rcl diff \
  examples/history/mobile-base-before \
  examples/history/mobile-base-after
```

The diff reports behavior additions/removals, semantic parameter changes, preservation/source/confidence changes, lifecycle changes, and history event additions/removals.

JSON output:

```bash
rcl diff before-profile after-profile --json
```

## Package compatibility

Habit history is embedded in the existing `behavior.json` payload. RCL does not add a sixth `.rcl` payload in v0.1, so the existing five-payload package structure remains unchanged.

Profiles that omit `habit` remain valid.

## Boundary

A recorded habit is a portable behavioral-history construct. RCL does not infer consciousness, emotional meaning, subjective identity, or legal identity from lifecycle labels or history events.
