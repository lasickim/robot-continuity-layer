# Intent Revision / Correction v0.1

Intent Revision exists because a long-lived robot can learn more about its own behavior over time.

An Intent that was reasonable when first approved may later be incomplete or wrong. RCL therefore does not treat an approved purpose as permanently unquestionable, and it does not permit silent overwrites.

```text
Declared Intent v1
        ↓
more experience / new evidence
        ↓
Revision Candidate
        ↓
preview
        ↓
explicit approval
        ↓
Declared Intent v2
        ↓
previous Intent retained in append-only history
```

## Approval and revision are different operations

`approve-intent` attaches the **first** declared Intent to a behavior that has none.

`revise-intent` changes an **existing** declared Intent while preserving what was previously believed.

A first attachment must not use revision, and an existing intent must not be overwritten by first-approval logic.

## Current intent vs history

RCL keeps these separate:

```text
behavior.intent
    current purpose used for continuity

behavior.intent_history[]
    previous intent snapshots plus revision evidence
```

Each history entry contains the exact previous `behavior.intent` object as `intent_snapshot`. Historical snapshots are descriptive/auditable; they are not replayed as current intent.

## Digest chain

Each revision records:

- SHA-256 of the previous Intent snapshot;
- SHA-256 of the new current Intent;
- revision candidate SHA-256;
- revision ID;
- approval time / actor;
- revision reason;
- evidence references;
- `causal_claim=false`.

For multiple revisions, validation requires a continuous chain:

```text
revision[0].to_intent_sha256
    == revision[1].from_intent_sha256

revision[1].to_intent_sha256
    == revision[2].from_intent_sha256

last.to_intent_sha256
    == SHA256(current behavior.intent)
```

Editing an old Intent snapshot without regenerating the complete legitimate revision chain therefore invalidates the profile.

## Revision candidate

A Revision Candidate is an engineering proposal, not an automatic mutation.

```json
{
  "revision_candidate_version": "0.1",
  "candidate_id": "seat-revision-001",
  "created_at": "2026-08-15T00:00:00Z",
  "behavior_id": "safety.pre_sit_clearance_check",
  "current_intent_sha256": "...",
  "replacement_intent": {
    "goal_id": "x.rcl-demo.verify_sitting_support_ready",
    "trigger": "activity.before_sit_down",
    "success_condition": "state.sitting_support_ready",
    "failure_action": "block",
    "criticality": "required",
    "required_capabilities": [
      "x.rcl-demo.sitting_support_observation"
    ]
  },
  "reason": "Later evidence indicates the check covers support readiness, not only clearance.",
  "evidence_refs": [
    "experience-summary://seat-support-2026-08"
  ],
  "causal_claim": false
}
```

The `current_intent_sha256` is a stale-data guard. If the profile's current Intent changed after the candidate was created, the candidate cannot be approved against the new state.

## Preview

```bash
rcl revise-intent preview \
  PROFILE \
  revision-candidate.json \
  safety.pre_sit_clearance_check \
  --approved-at 2026-08-15T01:00:00Z
```

Preview is deterministic and does not mutate files.

## Apply

```bash
rcl revise-intent apply \
  PROFILE \
  revision-candidate.json \
  safety.pre_sit_clearance_check \
  PROFILE_REVISED \
  --approved-at 2026-08-15T01:00:00Z \
  --approved-by demo-user
```

Apply:

1. validates the candidate and current-intent digest;
2. refuses a no-op semantic replacement;
3. checks approval chronology;
4. creates one revision-history entry containing the exact previous Intent;
5. creates fresh `source=revised` current provenance;
6. copies all five RCL payloads to a temporary sibling directory;
7. changes only `behavior.intent` and append-only `behavior.intent_history` for the selected behavior;
8. regenerates the manifest and SHA-256 values;
9. validates the output profile and Profile Diff;
10. verifies source payload bytes are unchanged;
11. atomically publishes the new snapshot.

## What revision does not change

Intent Revision does not modify:

- semantic behavior parameters;
- habit metadata;
- visible expression;
- behavior source/confidence;
- identity;
- preferences;
- skills;
- embodiment;
- safety precedence.

## Causality boundary

Revision means:

> Given later evidence, an explicit reviewer chose a better engineering purpose description for continuity.

It does **not** mean:

> The previous purpose was objectively false and the new purpose has been scientifically proven causal.

Every revision keeps `causal_claim=false`.

## Why this matters for continuity

A robot used for years should be allowed to become better understood without rewriting its past.

```text
Experience
  ↓
Interpretation v1
  ↓
more experience
  ↓
Correction v2
  ↓
more experience
  ↓
Correction v3
```

RCL carries both the current interpretation and the history of how that interpretation evolved.
