# Explicit Habit Approval / Profile Patch v0.1

Habit Promotion Policy only recommends a lifecycle transition. Explicit Habit Approval is the separate mutation step that a user or authorized higher-level policy must invoke intentionally.

```text
habit history + evidence
        ↓
Habit Promotion Policy
        ↓
candidate
        ↓
approval preview
        ↓
explicit review
        ↓
approval apply
        ↓
new RCL snapshot
```

## Non-automatic by design

The approval workflow never selects a candidate automatically. The caller must name the behavior ID and provide an approval timestamp.

A blocked or terminal promotion decision cannot be approved.

The promotion report must also refer to the same robot/generation/embodiment as the source profile, and its declared current lifecycle must still match the source profile. This prevents a stale promotion report from being replayed after the profile has already changed.

## Preview

```bash
rcl approve-habit preview \
  profile-before \
  promotion-report.json \
  navigation.follow_person \
  --approved-at 2026-08-14T06:00:00Z \
  --approved-by local-user
```

Preview returns a deterministic patch and does not write any profile files.

For a `learning -> stable` transition the patch normally contains:

```text
habit.lifecycle:
  learning -> stable

habit.stable_since:
  null -> approval timestamp

habit.user_confirmed_at:
  null -> approval timestamp   # only when not already present

history:
  + promotion_approved event
```

`configured -> learning` does not invent a stability timestamp. `stable -> legacy` sets `legacy_since`; an existing earlier `user_confirmed_at` is preserved.

## Apply

```bash
rcl approve-habit apply \
  profile-before \
  promotion-report.json \
  navigation.follow_person \
  profile-after \
  --approved-at 2026-08-14T06:00:00Z \
  --approved-by local-user
```

Apply refuses to overwrite an existing output path and refuses to create the output inside the source profile directory.

The implementation:

1. re-validates the promotion candidate;
2. builds the same deterministic preview patch;
3. copies the five RCL payloads into a temporary output directory;
4. modifies only the selected behavior's habit lifecycle/timestamp/history metadata;
5. validates the updated `behavior.json` including chronological history rules;
6. creates a new `manifest.json` with fresh SHA-256 hashes;
7. opens the temporary snapshot through normal `RCLProfile` validation;
8. runs Profile Diff and rejects the result if semantic `behavior.parameters` changed or another behavior changed;
9. verifies the source payload hashes are unchanged;
10. atomically renames the validated temporary directory to the requested output path.

## Determinism

For identical validated inputs, approval timestamp, approver metadata, and promotion report, preview produces the same patch and the same deterministic approval event ID.

The default output profile ID is derived from the source profile reference plus the canonical patch hash. A caller may explicitly provide another profile ID on apply.

## Approval history event

Approval appends one non-executable event:

```json
{
  "event_id": "approval-...",
  "observed_at": "2026-08-14T06:00:00Z",
  "event_type": "promotion_approved",
  "note": "Explicitly approved habit lifecycle transition learning -> stable by local-user.",
  "evidence_ref": "habit-promotion:rcl.habit.promotion.default.v0.1@0.1:..."
}
```

The event explains why the lifecycle changed. It is never replayed as a robot command.

## What approval does not change

Habit approval does not modify:

- semantic `behavior.parameters`;
- capabilities;
- migration results;
- safety policy;
- motor/joint commands;
- other behaviors.

`legacy` still cannot override target safety constraints.

## Schemas

Runtime and public schemas:

```text
rcl/schemas/habit-approval-patch.schema.json
rcl/schemas/habit-approval-result.schema.json
spec/schemas/habit-approval-patch.schema.json
spec/schemas/habit-approval-result.schema.json
```

## Boundary

An approval proves that an explicit RCL lifecycle mutation was requested and recorded. It does not prove consciousness, personal identity, emotional authenticity, or physical safety, and it does not imply that the underlying semantic behavior was automatically learned by the approval operation.
