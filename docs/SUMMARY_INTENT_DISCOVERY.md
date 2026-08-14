# Summary-Aware Intent Discovery v0.1

RCL can evaluate the same context-action-outcome hypothesis from either raw episodes or a compatible Experience Summary.

The purpose is long-lived evidence efficiency, not reconstruction of deleted observations.

```text
normal robot operation
        ↓
Experience Episodes
        ↓
compact-experience
        ↓
Experience Summary
        ↓
discover-intent-summary
        ↓
Intent Candidate / insufficient_evidence
```

## Why action-stratified summaries are required

The original Experience Summary retained:

- total outcome statistics;
- action-present count;
- action-absent count.

That is not enough to calculate the association used by Intent Discovery. Discovery needs the outcome separately for episodes where the candidate action occurred and where it did not.

New compaction output therefore also carries:

```json
{
  "action_strata": {
    "present": {
      "episode_count": 10,
      "outcomes": {
        "object_stability": {
          "type": "numeric",
          "count": 10,
          "mean": 0.952
        }
      }
    },
    "absent": {
      "episode_count": 10,
      "outcomes": {
        "object_stability": {
          "type": "numeric",
          "count": 10,
          "mean": 0.6
        }
      }
    }
  }
}
```

The existing combined `outcomes` field remains present for backward compatibility.

Older v0.1 summaries without `action_strata` still validate as Experience Summary artifacts, but summary-aware Intent Discovery rejects them. RCL does not estimate missing strata or create pseudo-episodes.

## Shared scoring core

Raw and aggregate evidence converge before scoring:

```text
raw episodes
  ↓
action-present / action-absent means
  ┐
  ├──→ shared Intent Discovery scoring + gates
  ┘
aggregate action strata
  ↓
weighted action-present / action-absent means
```

The same policy gates are then applied:

- matching context sample count;
- action-present sample count;
- action-absent sample count;
- action repetition rate;
- minimum meaningful beneficial effect.

For equivalent source data, raw and aggregate discovery should produce the same gate decisions, status, confidence, and effect values within the declared summary precision.

## Evidence basis and provenance

Every Intent Candidate report now declares its evidence basis.

Raw:

```json
{
  "evidence_basis": "raw",
  "evidence_provenance": {
    "basis": "raw",
    "dataset_digest_sha256": "...",
    "source_episode_count": 22
  }
}
```

Aggregate:

```json
{
  "evidence_basis": "aggregate",
  "evidence_provenance": {
    "basis": "aggregate",
    "summary_id": "experience-summary-...",
    "summary_method": "rcl.experience.compaction.semantic_groups.v0.1",
    "store_id": "robot-life-store",
    "source_digest_sha256": "...",
    "source_episode_count": 220000,
    "group_ids": ["experience-group-..."]
  }
}
```

This distinction survives Intent Approval because approval records the canonical candidate-report digest.

## CLI

First create a summary:

```bash
rcl compact-experience experience.json --output summary.json
```

Then provide a hypothesis containing:

```json
{
  "summary_hypothesis_version": "0.1",
  "dataset_id": "release-stability-review-001",
  "candidate_action_id": "interaction.post_release_hold",
  "context_match": {"task": "object_release"},
  "outcome": {
    "outcome_id": "object_stability",
    "type": "numeric",
    "higher_is_better": true,
    "minimum_meaningful_effect": 0.15,
    "unit": "ratio"
  },
  "proposed_intent": {
    "goal_id": "x.example.stabilize_released_object",
    "trigger": "activity.after_object_release",
    "success_condition": "state.released_object_stable",
    "failure_action": "retry",
    "criticality": "preferred",
    "required_capabilities": ["x.example.object_stability_observation"]
  }
}
```

Run:

```bash
rcl discover-intent-summary summary.json hypothesis.json --json
```

## What is not claimed

Aggregate evidence is not raw evidence. A summary cannot recover timing detail, distribution shape, correlations between multiple fields, sensor frames, or observations that were never retained.

Summary-aware discovery therefore does not:

- reconstruct raw episodes;
- prove causality;
- infer subjective motivation;
- approve an Intent Candidate;
- authorize raw-data deletion;
- claim that aggregate statistics preserve every future analysis possibility.

`causal_claim=false` remains mandatory.
