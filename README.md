# Robot Continuity Layer (RCL)

**Experimental open specification · semantic/reference implementation `0.4.0-dev`**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an experimental open specification and reference implementation for carrying a robot's **portable continuity** across hardware changes: identity metadata, preferences, semantic behavior, habits and history, declared functional intent, familiar expression, long-lived experience evidence, and provenance needed to review those claims.

RCL does **not** require Robot B to mechanically imitate every limitation of Robot A. The new body should use its own better sensors, actuators, controllers, planners, and safety systems while preserving the purpose, experience, and recognizable manner that should survive the hardware change.

> **Start here:** [`docs/V0.4_OVERVIEW.md`](docs/V0.4_OVERVIEW.md) is the concise external-facing description of the frozen v0.4 capability surface.

## Project status

```text
semantic/reference implementation   0.4.0-dev
.rcl archive/package format         0.2 compatible
v0.4 capability surface             FROZEN for polish
next major direction                physical Robot A → Robot B validation
```

The `.rcl` package remains the same five portable payloads plus a manifest:

```text
manifest.json
identity.json
preferences.json
behavior.json
skills.json
embodiment.json
```

v0.4 expands the semantics and supporting evidence/governance artifacts without breaking that archive layout.

For development detail, see [`docs/V0.4_CHECKPOINT.md`](docs/V0.4_CHECKPOINT.md). For planned work, see [`ROADMAP.md`](ROADMAP.md). For version history, see [`CHANGELOG.md`](CHANGELOG.md).

## 30-second explanation

```text
Robot A lives with a user
        ↓
experience / preferences / habits / WHY / expression accumulate
        ↓
RCL stores portable semantic continuity
        ↓
Robot A is replaced
        ↓
Robot B imports the continuity profile
        ↓
Robot B uses its own native hardware for the real function
        +
preserves familiar behavior where safe and feasible
        ↓
RCL measures what was preserved, what changed, and why
```

The compact mental model is:

> **Use the new body. Preserve the old manner.**

## The semantic split

RCL keeps several concepts deliberately separate:

```text
WHY      → Intent / functional goal
WHAT     → semantic behavior + parameters
HOW      → embodiment adapter / target-native execution strategy
LOOKS    → recognizable expression / mannerism
TEMPO    → expressive temporal style
HISTORY  → habits, legacy behavior, prior Intent and Expression interpretations
```

That separation allows Robot B to use a completely different physical strategy while preserving the same functional reason and, where appropriate, the familiar visible manner.

Example:

```text
Robot V1
rearward turn → camera check → safe to sit

Portable WHY
verify sitting area is clear before sitting

Robot V2
rear depth sensing → clearance verified
                   ↓
optional familiar rearward glance
                   ↓
sit
```

V2 uses its new sensing system immediately for the function. The old glance may remain as expression if it is safe and meaningful; old hardware delay does not become a requirement.

## Five continuity principles

> **Use the new body. Preserve the old manner.**
>
> **Preserve the gesture, not the limitation.**
>
> **Preserve by default. Optimize only by explicit approval.**
>
> **Recommend automatically. Change only by explicit approval.**
>
> **Preserve the goal, not one body's capability recipe.**

## v0.4 architecture in one flow

```text
Robot operation
   ↓
Experience Episodes
   ↓
Compaction
   ↓
Retention / Archive policy
   ↓
Provenance / Privacy governance
   ↓
RAW or AGGREGATE Habit evidence
   ↓
Habit review / explicit approval
   ↓
Human / Rule / LLM / VLM WHY proposal
   ↓
Intent Discovery
   ↓
Context Diagnostics
   ↓
Explicit Intent Approval
   ↓
Intent Revision / append-only history
   ↓
Goal Vocabulary Governance
   ↓
Alternative Capability Paths
   ↓
Adapter Migration / target-native HOW
   ↓
Expression + Expressive Timing
   ↓
Observed Intent Success
   ↓
Repeated Intent Success
   ↓
separate motion/statistical continuity evaluation
```

No one stage silently substitutes for another.

## What works today

### Portable profile and migration

RCL can validate and package `.rcl` profiles with SHA-256 manifests, describe source and target embodiments through semantic capabilities, migrate semantic behavior through adapters, report `preserved / approximated / unsupported / blocked_for_safety`, and calculate the declared Behavior Continuity Score.

A required behavior or required Intent that cannot be represented safely remains an explicit migration failure rather than being hidden by an average score.

### Intent, capability paths, and conformance

RCL can preserve a declared engineering WHY separately from visible motion. One Intent may expose multiple semantic capability paths, so different target bodies can satisfy the same goal through different target-native strategies.

```text
same WHY
  ↓
Path A OR Path B OR Path C
  ↓
different target-native HOW
```

Intent-aware Adapter Conformance independently re-evaluates available capability paths and catches adapters that flatten alternatives, falsely claim a selected path, or substitute visible expression for required Intent.

See:
- [`docs/BEHAVIOR_INTENT.md`](docs/BEHAVIOR_INTENT.md)
- [`docs/CAPABILITY_PATHS.md`](docs/CAPABILITY_PATHS.md)
- [`docs/CAPABILITY_REGISTRY.md`](docs/CAPABILITY_REGISTRY.md)
- [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md)

### WHY proposal, discovery, review, and correction

Humans, rules, LLMs, VLMs, external models, or other plugins can submit the same neutral Intent Hypothesis Proposal envelope.

```text
proposer
→ suggests WHY

evidence
→ supports or fails to support that WHY

approval
→ decides whether it becomes continuity metadata
```

A proposer's self-confidence is audit metadata only. It never becomes RCL confidence or approval authority.

Intent Discovery evaluates context-action-outcome association without claiming causality. Context Diagnostics can warn when pooled evidence appears dependent on narrower observed conditions. Eligible candidates require explicit Intent Approval, and later evidence may produce an explicit Intent Revision while preserving the previous interpretation in append-only history.

See:
- [`docs/INTENT_HYPOTHESIS_PROPOSER.md`](docs/INTENT_HYPOTHESIS_PROPOSER.md)
- [`docs/INTENT_DISCOVERY.md`](docs/INTENT_DISCOVERY.md)
- [`docs/SUMMARY_INTENT_DISCOVERY.md`](docs/SUMMARY_INTENT_DISCOVERY.md)
- [`docs/INTENT_CONTEXT_DIAGNOSTICS.md`](docs/INTENT_CONTEXT_DIAGNOSTICS.md)
- [`docs/INTENT_APPROVAL.md`](docs/INTENT_APPROVAL.md)
- [`docs/INTENT_REVISION.md`](docs/INTENT_REVISION.md)

### Goal vocabulary governance

Projects may freely experiment with extension goals under:

```text
x.<owner>.<semantic_path>
```

When a project wants an experimental WHY to become shared RCL vocabulary, Goal Vocabulary Governance adds deterministic review assistance plus an explicit human decision boundary.

> **Experiment freely; standardize deliberately.**

Approval authorizes a vocabulary-change proposal; it does not silently edit the standard vocabulary file.

See [`docs/GOAL_VOCABULARY_GOVERNANCE.md`](docs/GOAL_VOCABULARY_GOVERNANCE.md).

### Experience lifecycle and long-lived evidence

RCL records lightweight semantic Context + Action + Outcome episodes without requiring an unlimited raw-media archive.

```text
small semantic episode
   ↓
non-destructive compaction
   ↓
aggregate evidence
   ↓
retention review
   ↓
RETAIN | ARCHIVE_CANDIDATE | PRUNE_CANDIDATE
```

Important boundaries:

> **Compaction is not deletion consent.**

`PRUNE_CANDIDATE` does not mean deleted. Archive records are deployment assertions bound to exact source digests; RCL does not claim to inspect remote storage bytes.

Habit Evidence can consume either raw Experience or compatible aggregate summaries. Aggregate evidence never pretends to be raw experience and never reconstructs pseudo-episodes or synthetic habit-history events.

See:
- [`docs/EXPERIENCE_STORE.md`](docs/EXPERIENCE_STORE.md)
- [`docs/EXPERIENCE_RETENTION.md`](docs/EXPERIENCE_RETENTION.md)
- [`docs/HABIT_EVIDENCE.md`](docs/HABIT_EVIDENCE.md)
- [`docs/HABIT_HISTORY.md`](docs/HABIT_HISTORY.md)
- [`docs/HABIT_PROMOTION.md`](docs/HABIT_PROMOTION.md)
- [`docs/HABIT_APPROVAL.md`](docs/HABIT_APPROVAL.md)

### Provenance and privacy governance

RCL can bind a companion provenance/privacy record to a canonical JSON artifact and carry parent lineage, declared privacy classification, sharing scope, transformation metadata, and external evidence-reference rules across derived artifacts.

Reference ordering:

```text
public < internal < private < restricted
```

Two key rules:

> **Provenance is not permission.**
>
> **Aggregation does not automatically declassify data.**

A derived artifact cannot silently lower its classification or broaden its sharing scope beyond governed parents. Operation review remains non-mutating; RCL does not perform the share, archive, copy, or prune itself and does not inspect content to infer legal privacy status.

See [`docs/PROVENANCE_PRIVACY.md`](docs/PROVENANCE_PRIVACY.md).

### Expression, timing, and explicit optimization

RCL separates recognizable manner from functional execution.

A source gesture can remain even if the new body no longer needs that gesture for the function. Hardware-caused slowness is not automatically normative; user-valued or recognized timing can be represented semantically and realized using safe target-native timing.

RCL may generate a non-mutating recommendation to review simplification/removal, but actual change requires explicit approval and creates a new immutable snapshot. Previous expressions remain in append-only `expression_history`.

See:
- [`docs/EXPRESSIVE_TIMING.md`](docs/EXPRESSIVE_TIMING.md)
- [`docs/EXPRESSION_RECOMMENDATION.md`](docs/EXPRESSION_RECOMMENDATION.md)
- [`docs/EXPRESSION_OPTIMIZATION.md`](docs/EXPRESSION_OPTIMIZATION.md)

### Observed and repeated validation

RCL keeps representability, execution success, behavioral similarity, and physical safety separate.

```text
Capability Path
→ can this body represent a declared route to the goal?

Adapter Conformance
→ is the adapter reporting that route honestly?

Observed Intent Success
→ did one execution actually satisfy the declared success condition?

Repeated Intent Success
→ does that WHY keep being satisfied across repeated trials/sessions?

Observed / Statistical Continuity
→ how similar was the observable behavior?

Physical validation
→ is the real robot safe and suitable in the actual environment?
```

A required failure remains explicit even when an aggregate success rate is high.

See:
- [`docs/OBSERVED_INTENT_SUCCESS.md`](docs/OBSERVED_INTENT_SUCCESS.md)
- [`docs/REPEATED_INTENT_SUCCESS.md`](docs/REPEATED_INTENT_SUCCESS.md)
- [`docs/OBSERVED_EVALUATION.md`](docs/OBSERVED_EVALUATION.md)
- [`docs/STATISTICAL_CONTINUITY.md`](docs/STATISTICAL_CONTINUITY.md)
- [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md)
- [`docs/SESSION_CONFIDENCE.md`](docs/SESSION_CONFIDENCE.md)

## What RCL does not claim

RCL does **not** claim to:

- transfer consciousness, personhood, or subjective identity;
- infer subjective motivation;
- prove causality from observational association;
- make an LLM/VLM authoritative over robot continuity;
- define one universal natural movement speed;
- require source hardware limitations on a target body;
- treat target incompatibility as permission to forget history;
- reconstruct discarded raw evidence from summaries;
- automatically delete, archive, share, or prune user data;
- infer legal privacy status or consent from content;
- replace encryption, PKI, access control, or deployment security infrastructure;
- certify physical robot safety;
- replace ROS 2, robot controllers, planners, or vendor-specific execution stacks.

RCL standardizes portable semantic continuity, evidence, migration reporting, review boundaries, and conformance—not every command a robot can execute.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

rcl validate examples/mobile-base
rcl capabilities list
pytest -q
```

A few useful v0.4 commands:

```bash
# Long-lived semantic experience
rcl compact-experience examples/experience/mixed-robot-life.episodes.json \
  --output /tmp/experience-summary.json

# Intent discovery from raw evidence
rcl discover-intent \
  examples/intent-discovery/object-release-stability.dataset.json

# Inspect a human/rule/LLM/VLM WHY proposal
rcl inspect-intent-proposal \
  examples/intent-proposer/llm-object-release.proposal.json

# Evaluate one execution against declared Intent
rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json

# Adapter protocol conformance
rcl-conformance intent rcl:CapabilityPathReferenceAdapter
```

See each feature document for complete CLI examples and report formats.

## Development and compatibility

The public core is intentionally model-neutral and vendor-neutral. New robot-specific execution logic belongs in adapters; experimental capabilities and goals use extension namespaces rather than silently claiming standard semantics.

Compatibility and contribution guidance:

- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## v0.4 freeze boundary

The major planned v0.4 software/spec capability areas are represented. During the v0.4 polish line:

```text
new conceptual capability area     → later version
bug / safety / validation fix      → allowed
documentation correction           → allowed
schema inconsistency correction    → allowed
release-story consolidation        → allowed
```

This boundary is documented in [`docs/V0.4_OVERVIEW.md`](docs/V0.4_OVERVIEW.md).

## v0.5 direction: physical continuity evidence

The next major direction is real Robot A → Robot B evidence rather than more configuration-only feature growth.

A physical validation sequence may look like:

```text
Robot A repeated behavior
        ↓
semantic observations / Experience
        ↓
RCL profile + evidence
        ↓
Robot B migration
        ↓
target-native execution
        ↓
Intent Success + behavior similarity + repeated sessions
        ↓
physical safety / user review
```

Human-interaction tasks such as handover or handshake-style behavior are useful candidate scenarios because they can expose functional success, expression, timing, and relationship-context continuity at the same time. RCL should preserve behavior that was actually experienced; it should not fabricate source experience for previously unseen contexts.

See [`ROADMAP.md`](ROADMAP.md) for the v0.5 validation plan.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
