# Provenance / Privacy Governance v0.1

RCL carries long-lived robot continuity data across time and hardware changes. That makes two questions unavoidable:

1. **Where did this artifact come from?**
2. **What operations are allowed on it?**

Those questions are related, but they are not the same.

> **Provenance is not permission.**

Knowing the source of an artifact does not mean it may be published, shared, archived, or pruned without review.

A second rule is equally important:

> **Aggregation does not automatically declassify data.**

A compacted summary of private experience does not become public merely because the raw episodes were reduced to statistics.

## Concept

```text
RCL JSON artifact
        ↓
Provenance / Privacy Record
        ↓
artifact SHA-256
origin / actor
parent lineage
transformation
privacy declaration
        ↓
requested operation
        ↓
ALLOWED | BLOCKED
```

The record is a **companion artifact**. It does not add a new required payload to the existing `.rcl` package layout.

## What the record binds

A v0.1 record contains:

```text
artifact ID + type
canonical JSON SHA-256
created_at / created_by
origin kind
optional source reference
parent record lineage
transformation metadata for derived artifacts
privacy classification
sharing scope
external evidence-reference policy
```

The artifact digest protects against a record being silently reused after the artifact changed.

Parent links bind both:

```text
parent provenance record SHA-256
+
parent artifact SHA-256
```

so a derived artifact cannot casually point to a modified parent record.

## Origin kinds

Reference origin kinds are:

```text
sensor
user
operator
imported
model
derived
system
other
```

`derived` has stronger requirements:

```text
at least one parent provenance record
+
transformation method
```

A non-derived artifact cannot pretend to have transformation lineage in v0.1.

## Privacy classifications

RCL v0.1 uses an engineering ordering:

```text
public
  ↓ more restrictive
internal
  ↓
private
  ↓
restricted
```

These labels are deployment declarations. RCL does **not** inspect content and decide whether something is legally personal or sensitive information.

```text
content_privacy_inferred = false
```

## Sharing scopes

Privacy classification and sharing scope are separate.

```text
local_only
approved_recipients
public
```

Examples:

```text
private + local_only
→ local use may be allowed
→ approved share blocked
→ public share blocked

private + approved_recipients
→ local use allowed
→ approved share may be allowed
→ public share blocked

public + public
→ public share may be allowed
```

## Derived artifacts cannot silently become less restricted

Suppose a source Experience Store is:

```text
classification = private
sharing_scope  = approved_recipients
```

A derived Summary may remain:

```text
private + approved_recipients
```

or become more restrictive.

It may **not** automatically become:

```text
public + public
```

The same monotonic rule applies to external evidence-reference propagation and content-copy permission.

v0.1 intentionally has no automatic declassification workflow.

## External evidence references

Semantic RCL artifacts may refer to externally managed sensor/video/audio/log evidence.

The artifact being shareable does not automatically authorize those references or external bytes to follow it.

The provenance record therefore declares:

```text
external_evidence_refs.propagation
= exclude | approved_recipients | public

external_evidence_refs.content_copy
= not_permitted | deployment_permitted
```

For example, a public semantic report can still say:

```text
propagation = exclude
```

which prevents a public-share review from including its external evidence references.

Even `deployment_permitted` is only a declaration used by the review. RCL does not copy the external bytes.

## Requested operations

The reference policy reviews:

```text
local_use
share_approved
share_public
archive
prune_review
```

The output is only:

```text
ALLOWED
or
BLOCKED
```

No operation is executed.

Every report states:

```text
non_mutating = true
share_executed = false
archive_executed = false
prune_executed = false
content_privacy_inferred = false
```

## CLI

Create a provenance/privacy companion record:

```bash
rcl record-artifact-provenance artifact.json \
  --artifact-id experience-summary-001 \
  --artifact-type experience.summary \
  --created-at 2026-08-16T00:00:00Z \
  --created-by compactor \
  --origin-kind derived \
  --classification private \
  --sharing-scope approved_recipients \
  --parent-record source.provenance.json \
  --parent-relationship summarized_from \
  --transformation-method rcl.experience.compaction.semantic_groups.v0.1 \
  --output summary.provenance.json
```

Review an operation:

```bash
rcl evaluate-artifact-governance \
  artifact.json \
  summary.provenance.json \
  --parent-record source.provenance.json \
  --operation share_approved
```

Machine-readable output is available with `--json`.

Exit codes for evaluation:

```text
0 allowed
7 blocked
2 invalid input / stale lineage / digest mismatch
```

## Relationship to Experience lifecycle

```text
Experience Store
   ↓
Compaction
   ↓
Summary
   ↓
Retention / Archive
   ↓
Habit / Intent evidence
```

Provenance / Privacy Governance can accompany any of those JSON artifacts and preserve declared lineage/privacy constraints across the chain.

It complements retention policy rather than replacing it:

- retention asks what may remain active/archive/prune-review;
- privacy governance asks whether the requested operation is allowed for the declared artifact/lineage policy.

## What v0.1 does not do

It does not:

- determine whether data is legally personal information;
- infer consent;
- inspect content to assign privacy labels;
- implement encryption;
- implement authentication/authorization infrastructure;
- upload or share files;
- move archive objects;
- delete evidence;
- verify external storage bytes;
- provide legal or regulatory compliance certification.

It is a deterministic engineering metadata and policy layer for auditable robot-continuity artifacts.
