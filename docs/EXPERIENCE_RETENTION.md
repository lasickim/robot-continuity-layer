# Experience Retention / Archive / Prune Policy v0.1

RCL can compact long-lived Experience Store episodes into aggregate evidence, but **a summary is not permission to delete its source**.

The v0.1 retention layer adds an explicit lifecycle review between compaction and any future destructive storage action.

> **Compaction is not deletion consent. Pruning requires verified summary evidence and an explicit retention lifecycle.**

## Concept first

```text
raw Experience Store
        ↓
non-destructive compaction
        ↓
Experience Summary
        ↓
verify summary against exact current source
        ↓
Retention Policy
        ↓
RETAIN
ARCHIVE_CANDIDATE
PRUNE_CANDIDATE
        ↓
explicit deployment/human action later
```

RCL v0.1 does not delete source episodes or move remote objects.

## The three decisions

### `retain`

Keep the source episode in the active raw store under the current policy.

Typical reasons include:

- the episode is still inside the active-retention window;
- it is a retained summary exemplar;
- it carries an external `evidence_refs` link and the policy protects those links;
- its semantic group is too small for pruning;
- the group has already reached its maximum prune-candidate fraction.

### `archive_candidate`

The episode is old enough and sufficiently represented by verified aggregate evidence, but an explicit archive record is required before pruning can even be considered.

This means:

```text
copy elsewhere may be appropriate
source deletion is NOT authorized
```

### `prune_candidate`

The episode satisfies the policy's eligibility rules and, under the default policy, an archive record covers the exact episode and exact source-store digest.

This means only:

```text
eligible for a later explicit prune workflow
```

It does **not** mean that RCL deleted anything.

Every retention report states:

```text
non_mutating = true
prune_executed = false
archive_executed_by_rcl = false
```

## Verified summary binding

Retention decisions do not trust a summary merely because a JSON file exists.

Before lifecycle evaluation, RCL verifies the supplied summary against the current source Experience Store:

```text
store_id
source episode count
full source SHA-256
semantic group IDs
context / action / outcome-key grouping
group episode counts
action-present / action-absent counts
outcome aggregate statistics
action-stratified statistics
source episode-ID digests
retained exemplar membership
```

If the source changed after compaction, the old summary is stale and retention evaluation stops.

If summary statistics were modified independently of the source evidence, retention evaluation also stops.

## Conservative default policy

The bundled v0.1 policy is intentionally conservative:

```json
{
  "policy_id": "rcl.experience.retention.conservative",
  "policy_version": "0.1",
  "min_active_retention_days": 30,
  "protect_retained_exemplars": true,
  "protect_external_evidence_refs": true,
  "min_group_episode_count_for_prune": 8,
  "max_prune_fraction_per_group": 0.5,
  "require_archive_record_for_prune": true
}
```

These are reference defaults, not universal legal or product-retention requirements.

Deployments may use another schema-valid policy.

## Why protect exemplars?

Compaction retains deterministic early and late exemplar episode IDs as longitudinal anchors.

Deleting those immediately after creating the summary would weaken the reason they were retained in the first place.

The default lifecycle therefore keeps them active.

## Why protect `evidence_refs`?

An Experience Episode may contain a pointer such as:

```json
{
  "evidence_refs": ["sensor-archive://release-103"]
}
```

The referenced bytes are not stored inside the Experience Store, but the semantic episode may be the link that explains what those bytes mean.

The default policy therefore keeps such episodes active. A deployment can explicitly disable this protection if its own provenance model preserves the relationship elsewhere.

## Sparse-group protection

A rare event should not become easier to discard merely because it occurred infrequently.

Under the default policy, groups with fewer than eight source episodes do not produce prune candidates.

```text
common repeated behavior
→ compaction may support lifecycle reduction

rare semantic experience
→ preserve raw evidence by default
```

## Per-group prune cap

Even when many old episodes have been archived, v0.1 keeps a deterministic active-store remainder.

The default maximum is:

```text
50% of each semantic group's source episodes
```

Only the oldest otherwise-eligible episodes are marked as prune candidates first.

Anything beyond the cap remains `retain` with reason:

```text
prune_fraction_guard
```

Again, this is a candidacy limit, not an automatic deletion percentage.

## Archive Record

RCL can create a non-mutating record such as:

```text
source store SHA-256
+ exact episode ID set
+ archived_at
+ archived_by
+ external location_ref
```

The record declares:

```text
archive_assertion = deployment_asserted_external_copy
archive_executed_by_rcl = false
```

This is intentionally modest.

RCL does not claim that it connected to S3, a NAS, a database, tape storage, or another remote system and verified the archived bytes. The deployment asserts that the copy exists; RCL binds that assertion to exact continuity evidence.

If the source store later changes, the old archive record becomes stale for that new source snapshot.

## CLI

Create an archive record after the deployment has performed its storage operation:

```bash
rcl record-experience-archive \
  examples/experience/retention-demo.episodes.json \
  --episode-id table-04 \
  --episode-id table-05 \
  --location-ref archive://cold-store/retention-demo/001 \
  --archived-at 2026-03-31T12:00:00Z \
  --archived-by operator@example.org \
  --output archive-record.json
```

Then evaluate lifecycle state:

```bash
rcl evaluate-experience-retention \
  examples/experience/retention-demo.episodes.json \
  experience-summary.json \
  --archive-record archive-record.json \
  --as-of 2026-04-01T12:00:00Z
```

Use `--json` for machine-readable stdout or `--output` to write the retention report.

## Python API

```python
from rcl.experience_retention import (
    create_experience_archive_record,
    evaluate_experience_retention,
    load_default_experience_retention_policy,
    validate_experience_archive_record,
    verify_experience_summary_binding,
)
```

The API accepts ordinary dictionaries and remains independent of any cloud-storage SDK.

## What this does not do

Experience Retention v0.1 does not:

- delete source episodes;
- move files or database rows;
- verify remote archive bytes;
- infer user consent to erase history;
- define GDPR, HIPAA, industrial, or other legal retention requirements;
- erase raw media referenced outside RCL;
- treat aggregate evidence as identical to raw evidence;
- replace deployment-specific backup, privacy, or records-management policy.

It provides an auditable semantic lifecycle layer so long-lived robot experience does not grow forever **and** is not silently forgotten merely because a compacted summary exists.
