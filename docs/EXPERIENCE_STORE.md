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

## Action-stratified evidence

Compaction also records outcome summaries separately for:

```text
action present
action absent
```

This allows summary-aware Intent Discovery and context diagnostics to compare association evidence without reconstructing pseudo-episodes.

Aggregate evidence remains aggregate evidence; RCL does not pretend a compacted statistic is a recovered raw observation.

## Provenance

Every summary contains:

- a SHA-256 digest of the complete source episode set;
- a deterministic digest of the source episode IDs for each group;
- source episode counts;
- deterministic exemplar episode IDs.

The default exemplar selection retains both early and late observations so a compacted group still has longitudinal anchors.

This provenance does not make an aggregate equivalent to raw evidence. It makes the relationship auditable.

## Non-destructive compaction boundary

Compaction itself never deletes episodes.

Every summary contains:

```json
{
  "destructive": false
}
```

The input object is also checked for accidental mutation by the reference implementation.

The rule remains:

> **Creating a summary is not consent to delete source evidence.**

## Retention / Archive / Prune lifecycle

RCL v0.4 now has a separate explicit lifecycle policy after compaction.

```text
raw source
   ↓
compaction
   ↓
summary
   ↓
verify summary against exact current source
   ↓
retention policy
   ↓
retain | archive_candidate | prune_candidate
```

This lifecycle remains non-destructive.

`prune_candidate` means only that a later explicit prune workflow may consider the episode. It does not remove an episode from the active store.

The conservative default protects:

- recent raw episodes;
- retained summary exemplars;
- episodes carrying external `evidence_refs`;
- sparse semantic groups;
- a deterministic per-group remainder through a maximum prune-candidate fraction.

Before an episode becomes a prune candidate under the default policy, a deployment-asserted Archive Record must cover the exact source-store digest and episode ID.

See [`EXPERIENCE_RETENTION.md`](EXPERIENCE_RETENTION.md).

## Archive Record boundary

An Archive Record says that the deployment asserts an external copy exists at a `location_ref`.

It does **not** say that RCL itself performed the copy or inspected the remote bytes.

```text
archive_executed_by_rcl = false
```

This distinction keeps RCL vendor-neutral: the external archive could be a database, object store, NAS, tape system, or another deployment-specific mechanism.

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

Compact experience:

```bash
rcl compact-experience \
  examples/experience/mixed-robot-life.episodes.json \
  --output /tmp/experience-summary.json
```

The number of retained exemplar IDs can be changed without deleting source data:

```bash
rcl compact-experience episodes.json \
  --retained-exemplars 8 \
  --output summary.json
```

Review lifecycle after compaction:

```bash
rcl evaluate-experience-retention \
  episodes.json \
  summary.json \
  --as-of 2026-04-01T12:00:00Z
```

Record a deployment-asserted external archive after the deployment has performed that storage operation:

```bash
rcl record-experience-archive episodes.json \
  --episode-id release-001 \
  --location-ref archive://cold-store/release-001 \
  --archived-at 2026-04-01T11:00:00Z \
  --archived-by operator@example.org \
  --output archive-record.json
```

## Relationship to Intent Discovery

The Experience Store is **upstream** of Intent Discovery.

```text
neutral experience records
        ↓
compaction / indexing
        ↓
human / rule / LLM / VLM proposes a WHY hypothesis
        ↓
Intent Discovery evaluates raw or aggregate evidence
        ↓
Context Diagnostics
        ↓
Intent Candidate review / explicit approval
```

Summary-aware evaluation consumes declared aggregate counts/statistics directly and never reconstructs fake episodes.

## Scope boundary

Experience Store + Compaction + Retention is not:

- model training;
- causal inference;
- automatic habit promotion;
- automatic intent approval;
- a raw-media archive;
- automatic deletion;
- remote storage execution;
- legal/compliance retention policy.

It is a lightweight continuity-data storage, evidence-summary, and explicit lifecycle-review layer.
