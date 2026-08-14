# Explicit Intent Approval / Profile Patch v0.1

Intent Discovery produces a reviewable **Intent Candidate**. It never writes `behavior.intent` by itself.

Intent Approval is the explicit mutation boundary that allows a user or authorized operator to accept that engineering hypothesis into continuity data.

```text
Experience
  ↓
Intent Discovery
  ↓
Intent Candidate
  ↓
preview
  ↓
explicit approval
  ↓
new immutable RCL snapshot
  ↓
Declared Intent + provenance
```

## Why approval is separate

A strong association is still not causal proof. A robot may repeat an action near a successful outcome for reasons not represented in the current dataset.

RCL therefore separates:

```text
candidate = evidence says "review this hypothesis"
approval  = a human/operator chooses to preserve this hypothesis
intent    = the purpose now declared for continuity
```

Approval does not rewrite history and does not upgrade `causal_claim` to true.

## Preconditions

`preview_intent_approval()` and `apply_intent_approval()` require all of the following:

- the report validates as Intent Candidate Report v0.1;
- `status == candidate`;
- `recommended_next_action == review_candidate`;
- confidence is `moderate` or `strong`;
- every evidence gate passed;
- `causal_claim == false`;
- `candidate_action_id` exactly equals the target `behavior_id`;
- the target behavior exists;
- the target behavior currently has no `intent`;
- `approved_at` is not earlier than the candidate report timestamp.

v0.1 intentionally refuses to overwrite an existing intent. Intent correction/replacement needs a future workflow with its own provenance and review rules.

## Preview

```bash
rcl approve-intent preview \
  examples/intent-approval/object-release-before \
  candidate-report.json \
  interaction.post_release_hold \
  --approved-at 2026-08-14T09:00:00Z \
  --approved-by local-user
```

Preview is deterministic for the same profile, candidate report, behavior ID, approval timestamp, and actor. It does not modify files.

The patch records:

- source robot / continuity generation / embodiment;
- source behavior canonical SHA-256;
- candidate ID and dataset ID;
- discovery method and confidence;
- canonical candidate-report SHA-256;
- the exact intent that will be added;
- approval actor/time;
- `causal_claim=false`.

## Apply

```bash
rcl approve-intent apply \
  examples/intent-approval/object-release-before \
  candidate-report.json \
  interaction.post_release_hold \
  /tmp/object-release-approved \
  --approved-at 2026-08-14T09:00:00Z \
  --approved-by local-user
```

Apply:

1. rebuilds the same deterministic preview patch;
2. refuses an existing output path or an output path inside the source profile;
3. copies the five portable payloads into a temporary new snapshot;
4. verifies the source behavior SHA-256 precondition;
5. adds only `behavior.intent`;
6. embeds approval provenance inside that intent;
7. regenerates `manifest.json` with fresh payload hashes;
8. validates the output profile;
9. runs Profile Diff;
10. rejects any semantic parameter or non-intent behavior change;
11. verifies that the source payload bytes remained unchanged;
12. atomically renames the temporary snapshot to the requested output directory.

## Approved intent provenance

A discovered-and-approved intent can carry:

```json
{
  "provenance": {
    "source": "discovered",
    "candidate_id": "intent-candidate-...",
    "dataset_id": "demo-object-release-stability-001",
    "discovery_method": "rcl.intent.discovery.context_action_outcome.v0.1",
    "policy_id": "rcl.intent.discovery.default.v0.1",
    "policy_version": "0.1",
    "candidate_report_sha256": "...",
    "approved_at": "2026-08-14T09:00:00Z",
    "approved_by": "local-user",
    "causal_claim": false
  }
}
```

This provenance travels with the declared intent. A later robot can therefore distinguish:

- what goal was declared;
- where the proposal came from;
- which evidence report was reviewed;
- who/when approved it;
- that the original evidence did not claim causal proof.

## What approval does not change

Intent Approval v0.1 must not modify:

- `behavior.parameters`;
- habit lifecycle/history;
- expression metadata;
- behavior source/confidence;
- other behaviors;
- identity or continuity generation;
- preferences;
- skills;
- embodiment.

It also never overrides target safety constraints.

## End-to-end example

```text
interaction.post_release_hold appears during use
        ↓
object stability is better when action is present
        ↓
Intent Discovery
        ↓
x.rcl-demo.stabilize_released_object
status=candidate
        ↓
user reviews evidence
        ↓
approve-intent
        ↓
new profile snapshot
        ↓
behavior.intent now declares the approved goal
        ↓
future embodiment adapters preserve WHY using target-native HOW
```

## Boundary

Intent Approval means:

> "Preserve this reviewed engineering goal hypothesis as part of this robot's continuity profile."

It does **not** mean:

- the hypothesis was causally proven;
- the robot has subjective motives;
- the user permanently waives future correction;
- the behavior is safe in every embodiment;
- the approved goal defines identity or personhood.
