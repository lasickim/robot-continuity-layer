# Lightweight Experience Store + Compaction v0.1

RCL separates **real-time robot operation** from **longitudinal experience analysis**.

The goal is not to keep a foundation model training continuously or archive every camera frame forever. Normal operation records small semantic episodes. Expensive or longitudinal analysis can happen later, such as while the robot is idle or charging.

```text
real-time control / perception
          ↓
small semantic episode
Context + Action + Outcome
          ↓
append-friendly Experience Store
          ↓
idle / charging / maintenance window
          ↓
Experience Compaction
          ↓
long-lived aggregate evidence
          ↓
Habit / Intent / evaluation workflows
```

## Experience Episode Set v0.1

An episode records only portable semantic evidence:

```json
{
  "episode_id": "release-001",
  "observed_at": "2026-08-10T09:00:00Z",
  "context": {
    "task": "object_release",
    "surface": "table"
  },
  "action": {
    "action_id": "interaction.post_release_hold",
    "performed": true,
    "parameters": {
      "duration_ms": 420
    }
  },
  "outcomes": {
    "object_stability": 0.96,
    "object_settled": true
  },
  "evidence_refs": [
    "sensor://release-001"
  ]
}
```

Raw image, video, or audio bytes are not part of this format. `evidence_refs` may point to externally managed data when a deployment chooses to retain it.

## Semantic grouping

Compaction groups episodes by:

```text
exact context
+
action_id
+
outcome-key set
```

It does not contain behavior-specific logic.

For example, object release and auto-docking episodes can be compacted by the same function without adding new code for either behavior.

Changing context creates a different group instead of silently averaging unlike conditions together.

## Numeric outcomes

Numeric values are summarized with:

- count
- mean
- sample standard deviation
- minimum
- maximum

The implementation uses the Python standard library only; no GPU or ML framework is required.

## Binary outcomes

Boolean values are summarized with:

- count
- true count
- false count
- true rate

A single semantic group may contain multiple outcomes, including both numeric and binary outcomes.

Mixed types for the **same outcome ID inside one semantic group** are rejected explicitly.

## Provenance

Every summary contains:

- a SHA-256 digest of the complete source episode set;
- a deterministic digest of the source episode IDs for each group;
- source episode counts;
- deterministic exemplar episode IDs.

The default exemplar selection retains both early and late observations so a compacted group still has longitudinal anchors.

This provenance does not make an aggregate equivalent to raw evidence. It makes the relationship auditable.

## Non-destructive v0.1 boundary

Compaction never deletes episodes.

Every summary contains:

```json
{
  "destructive": false
}
```

The input object is also checked for accidental mutation by the reference implementation.

Retention, prune, delete, or archival actions are deliberately deferred to a separate explicit future policy. Creating a summary is not consent to delete source evidence.

## Compute model

A practical deployment can use three different rates:

```text
real-time loop
100 Hz ~ 1 kHz
control / safety / perception

experience logging
on semantic events
small append operations

compaction / longitudinal analysis
minutes, hours, or charging windows
CPU background work
```

RCL itself does not require continual neural-network weight updates. A robot may use large perception or reasoning models elsewhere, but the Experience Store and Compaction layer remains model-independent and lightweight.

## CLI

```bash
rcl compact-experience \
  examples/experience/mixed-robot-life.episodes.json \
  --output /tmp/experience-summary.json
```

Human-readable output is the default. Use `--json` for a machine-readable report on stdout.

The number of retained exemplar IDs can be changed without deleting source data:

```bash
rcl compact-experience episodes.json \
  --retained-exemplars 8 \
  --output summary.json
```

## Relationship to Intent Discovery

The Experience Store is **upstream** of Intent Discovery.

```text
neutral experience records
        ↓
compaction / indexing
        ↓
a learning system or human proposes a hypothesis
        ↓
Intent Discovery evaluates evidence
        ↓
Intent Candidate
```

Intent Discovery v0.1 currently consumes episode datasets rather than compacted summaries directly. A future version may add summary-aware evidence evaluation, but it must preserve provenance and explicitly distinguish aggregate evidence from raw episode evidence.

## Scope boundary

Experience Compaction is not:

- model training;
- causal inference;
- automatic habit promotion;
- automatic intent approval;
- a raw-media archive;
- automatic retention/deletion policy.

It is a lightweight continuity-data storage and evidence-summary layer.
