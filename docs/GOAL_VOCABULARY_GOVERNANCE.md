# Goal Vocabulary Proposal / Review Governance v0.1

RCL lets projects experiment with their own Intent goals under:

```text
x.<owner>.<semantic_path>
```

That freedom should remain cheap.

A different question appears when a project wants one of those ideas to become a **shared RCL standard goal** used without the `x.<owner>` namespace.

> **Experiment freely; standardize deliberately.**

## User-level idea

```text
project-specific WHY
x.acme.verify_recipient_ready
        ↓
works across multiple implementations
        ↓
proposal for shared RCL vocabulary
        ↓
automated review assistance
        ↓
human review decision
        ↓
explicit repository/spec change
```

The governance workflow does **not** affect ordinary experimental extension goals.

## Why this exists

Without governance, several developers could independently add goals such as:

```text
safety.check_chair
safety.scan_seat_camera
safety.verify_sitting_area_clear
interaction.ensure_seat_empty
```

Some may describe the same purpose. Some may accidentally encode one robot's camera, joint, or controller strategy into what should be a portable WHY.

The proposal review makes those problems visible before a new shared name is treated as standard vocabulary.

## Proposal

A proposal records:

- the proposed shared `goal_id`;
- summary and semantic definition;
- trigger names;
- success-condition names;
- allowed failure actions;
- source experimental goal IDs, if any;
- why the goal is portable across bodies;
- supporting evidence/reference links;
- proposer identity and timestamp.

The proposal ID is deterministic and bound to the complete proposal material.

```text
proposal changed
→ expected proposal_id changes
→ old review cannot silently apply to the new proposal
```

## Automated review

```bash
rcl review-goal-proposal proposal.json
```

The reference implementation checks several classes of issue.

### Hard blockers

Examples:

```text
proposal ID no longer matches proposal contents
standard goal ID is malformed
standard goal ID already exists
source extension provenance is malformed
failure-action vocabulary is invalid
```

A blocked proposal cannot be approved.

### Advisory signals

Examples:

```text
new goal looks semantically similar to an existing shared goal
camera / LiDAR / GPIO / servo / joint wording appears in the portable definition
trigger naming looks implementation-specific
success condition is not expressed as a semantic state
```

Advisories produce `needs_revision`, but they do not remove human judgment.

A reviewer may still explicitly approve an advisory-only proposal when the distinction is justified and recorded.

## Review states

```text
ready_for_review
→ no detected blockers or advisories

needs_revision
→ no hard blocker, but one or more review signals exist

blocked
→ a hard structural/governance conflict exists
```

## Explicit decision record

```bash
rcl decide-goal-proposal \
  proposal.json \
  review.json \
  --decision approved \
  --reviewed-at 2026-08-15T15:10:00Z \
  --reviewed-by reviewer@example.org \
  --reason "Portable purpose accepted for standardization review" \
  --output decision.json
```

Possible decisions:

```text
approved
rejected
needs_revision
```

The decision record is bound to:

```text
exact proposal SHA-256
+
exact review-report SHA-256
```

Changing the proposal after review makes that review stale.

## Approval does not mutate the vocabulary

This is intentional.

```text
approved decision
        ↓
next_action = submit_explicit_vocabulary_change
        ↓
separate repository/spec change
        ↓
actual bundled vocabulary update
```

The governance tool never silently edits `intent-vocabulary-v0.1.json`.

This preserves ordinary code review, changelog history, test coverage, and explicit standard-vocabulary provenance.

## Experimental goals remain free

Projects can still use:

```text
x.acme.verify_recipient_ready
x.lab42.object_release_stability
x.vendor.some_new_goal
```

without asking the shared vocabulary governance workflow for permission.

Governance applies only when someone wants to claim a new **shared standard goal ID**.

## What automated review does not mean

A clean automated review does not prove that a proposed goal is universally correct.

Likewise, a semantic-overlap warning does not prove that two goals are identical.

The implementation deliberately separates:

```text
automated evidence / warnings
        ↓
human semantic judgment
        ↓
explicit standards-repository change
```

## Scope boundary

Goal Vocabulary Governance v0.1 is tooling for the draft RCL project's shared semantic vocabulary. It does not create formal standards-organization authority, legal certification, subjective Intent, causal proof, consciousness/personhood claims, or physical safety certification.
