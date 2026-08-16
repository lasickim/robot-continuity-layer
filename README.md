# Robot Continuity Layer (RCL)

**Experimental open specification · semantic/reference implementation `0.5.0-dev`**

> **Hardware can be replaced. Experience shouldn't be.**

RCL is an experimental open specification and reference implementation for carrying a robot's **portable continuity** across hardware changes: identity metadata, preferences, semantic behavior, habits and history, declared functional intent, familiar expression, long-lived experience evidence, and provenance needed to review those claims.

RCL does **not** require Robot B to mechanically imitate every limitation of Robot A. The new body should use its own sensors, actuators, controllers, planners, and safety systems while preserving the purpose, experience, and recognizable manner that should survive the hardware change.

> **Current development line:** [`docs/V0.5_DEVELOPMENT_LINE.md`](docs/V0.5_DEVELOPMENT_LINE.md)  
> **Frozen v0.4 overview:** [`docs/V0.4_OVERVIEW.md`](docs/V0.4_OVERVIEW.md)  
> **v0.4 release checkpoint:** [`docs/V0.4_RELEASE_CHECKPOINT.md`](docs/V0.4_RELEASE_CHECKPOINT.md)

## Project status

```text
semantic/reference implementation   0.5.0-dev
.rcl archive/package format         0.2 compatible
v0.4 capability surface             FROZEN + CHECKPOINTED
v0.5 current phase                  deterministic semantic simulation
next validation step                hardware-in-the-loop
ultimate v0.5 direction             physical Robot A → Robot B evidence
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

v0.5 starts from the frozen v0.4 semantics. It does not add a sixth required profile payload or redefine synthetic evidence as physical evidence.

For planned work, see [`ROADMAP.md`](ROADMAP.md). For version history, see [`CHANGELOG.md`](CHANGELOG.md).

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

RCL deliberately separates:

```text
WHY      → Intent / functional goal
WHAT     → semantic behavior + parameters
HOW      → embodiment adapter / target-native execution strategy
LOOKS    → recognizable expression / mannerism
TEMPO    → expressive temporal style
HISTORY  → habits, legacy behavior, prior Intent and Expression interpretations
```

Example:

```text
Robot A
rearward turn → camera/classifier check → safe to sit

Portable WHY
verify sitting area is clear before sitting

Robot B
direct rear clearance state → safe to sit
```

Robot B may satisfy the same WHY through a completely different HOW. A familiar source gesture may remain separately as expression when safe and representable; a target that cannot reproduce that gesture does not automatically fail functional Intent migration.

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

## v0.4 semantic capability foundation

The frozen v0.4 line established the software/spec foundation used by v0.5:

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

See [`docs/V0.4_OVERVIEW.md`](docs/V0.4_OVERVIEW.md) for the frozen capability surface and [`docs/V0.4_RELEASE_CHECKPOINT.md`](docs/V0.4_RELEASE_CHECKPOINT.md) for the validation record.

## v0.5: progressively stronger continuity evidence

v0.5 changes the emphasis from adding semantic capability areas to **testing the existing model with progressively stronger evidence**.

The validation ladder is:

```text
Phase 1 — deterministic semantic simulation
        ↓
Phase 2 — hardware-in-the-loop
        ↓
Phase 3 — low-cost physical Robot A / Robot B
        ↓
Phase 4 — richer manipulation / human-interaction validation
```

Evidence provenance must remain explicit:

```text
SIMULATION
→ deterministic or simulator-produced evidence

HIL
→ real compute/sensor/controller components with simulated or partial plant

PHYSICAL
→ actual robot measurements in a declared experiment context
```

Synthetic observations must never be presented as physical robot evidence.

### Phase 1 — Simulation Reference Experiment

The first v0.5 reference experiment is executable and deterministic.

```text
Robot A
perception.directional_attention
+ x.demo.rear_clearance_classifier
        ↓
source.rear_attention_clearance

same WHY
safety.verify_sitting_area_clear

Robot B
perception.sitting_area_clearance
        ↓
target.direct_clearance_state
```

Both sides provide three sessions × three trials of repeated Intent Success evidence. The experiment passes only when:

- source and target have sufficient repeated evidence for the same required Intent;
- migration succeeds;
- required Intent is preserved;
- Robot B selects the expected `direct_clearance` capability path;
- Robot A and Robot B use different observed strategy IDs;
- Robot B's observation agrees with the adapter's declared target-native strategy.

Robot B intentionally lacks the source expression capability, so the reference case expects:

```text
WHY preserved       → yes
HOW copied          → no
source LOOKS copied → no
migration succeeds  → yes
```

See [`docs/V0.5_SIMULATION_REFERENCE.md`](docs/V0.5_SIMULATION_REFERENCE.md).

## What works today

### Portable profile and migration

RCL can validate and package `.rcl` profiles with SHA-256 manifests, describe source and target embodiments through semantic capabilities, migrate semantic behavior through adapters, report `preserved / approximated / unsupported / blocked_for_safety`, and calculate the declared Behavior Continuity Score.

A required behavior or required Intent that cannot be represented safely remains an explicit migration failure rather than being hidden by an average score.

### Intent, capability paths, and conformance

One Intent may expose multiple semantic capability paths, so different target bodies can satisfy the same goal through different target-native strategies.

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

Humans, rules, LLMs, VLMs, external models, or other plugins can submit the same neutral Intent Hypothesis Proposal envelope. A proposer's self-confidence is audit metadata only; it never becomes RCL evidence or approval authority.

Intent Discovery evaluates context-action-outcome association without claiming causality. Context Diagnostics can warn when pooled evidence appears context-dependent. Eligible candidates require explicit Intent Approval, and later evidence may produce an explicit Intent Revision while preserving the previous interpretation in append-only history.

See:
- [`docs/INTENT_HYPOTHESIS_PROPOSER.md`](docs/INTENT_HYPOTHESIS_PROPOSER.md)
- [`docs/INTENT_DISCOVERY.md`](docs/INTENT_DISCOVERY.md)
- [`docs/SUMMARY_INTENT_DISCOVERY.md`](docs/SUMMARY_INTENT_DISCOVERY.md)
- [`docs/INTENT_CONTEXT_DIAGNOSTICS.md`](docs/INTENT_CONTEXT_DIAGNOSTICS.md)
- [`docs/INTENT_APPROVAL.md`](docs/INTENT_APPROVAL.md)
- [`docs/INTENT_REVISION.md`](docs/INTENT_REVISION.md)

### Experience, habits, provenance, and privacy

RCL records lightweight semantic Context + Action + Outcome episodes without requiring an unlimited raw-media archive. Compaction is non-destructive, retention review remains separate from deletion, and aggregate evidence never pretends to be raw experience.

> **Compaction is not deletion consent.**
>
> **Provenance is not permission.**
>
> **Aggregation does not automatically declassify data.**

See:
- [`docs/EXPERIENCE_STORE.md`](docs/EXPERIENCE_STORE.md)
- [`docs/EXPERIENCE_RETENTION.md`](docs/EXPERIENCE_RETENTION.md)
- [`docs/HABIT_EVIDENCE.md`](docs/HABIT_EVIDENCE.md)
- [`docs/HABIT_HISTORY.md`](docs/HABIT_HISTORY.md)
- [`docs/HABIT_PROMOTION.md`](docs/HABIT_PROMOTION.md)
- [`docs/HABIT_APPROVAL.md`](docs/HABIT_APPROVAL.md)
- [`docs/PROVENANCE_PRIVACY.md`](docs/PROVENANCE_PRIVACY.md)

### Expression, timing, and explicit optimization

RCL separates recognizable manner from functional execution. Hardware-caused slowness is not automatically normative; user-valued or recognized timing can be represented semantically and realized using safe target-native timing.

RCL may generate a non-mutating recommendation to review simplification/removal, but actual change requires explicit approval and creates a new immutable snapshot. Previous expressions remain in append-only history.

See:
- [`docs/EXPRESSIVE_TIMING.md`](docs/EXPRESSIVE_TIMING.md)
- [`docs/EXPRESSION_RECOMMENDATION.md`](docs/EXPRESSION_RECOMMENDATION.md)
- [`docs/EXPRESSION_OPTIMIZATION.md`](docs/EXPRESSION_OPTIMIZATION.md)

### Observed and repeated validation

RCL keeps representability, execution success, behavioral similarity, evidence provenance, and physical safety separate.

```text
Capability Path
→ can this body represent a declared route to the goal?

Adapter Conformance
→ is the adapter reporting that route honestly?

Observed Intent Success
→ did one execution satisfy the declared success condition?

Repeated Intent Success
→ does that WHY keep being satisfied across repeated trials/sessions?

Observed / Statistical Continuity
→ how similar was the observable behavior?

Physical validation
→ is the real robot safe and suitable in the actual environment?
```

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
- treat simulation or HIL evidence as real-robot evidence;
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

Run the v0.5 Phase 1 reference experiment:

```bash
python examples/v0.5-sim/run_reference_experiment.py
```

A few established semantic/evidence commands:

```bash
rcl compact-experience examples/experience/mixed-robot-life.episodes.json \
  --output /tmp/experience-summary.json

rcl discover-intent \
  examples/intent-discovery/object-release-stability.dataset.json

rcl inspect-intent-proposal \
  examples/intent-proposer/llm-object-release.proposal.json

rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json

rcl-conformance intent rcl:CapabilityPathReferenceAdapter
```

## Development and compatibility

The public core is intentionally model-neutral and vendor-neutral. New robot-specific execution logic belongs in adapters; experimental capabilities and goals use extension namespaces rather than silently claiming standard semantics.

Compatibility and contribution guidance:

- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## Version boundaries

### v0.4

The v0.4 semantic capability surface is frozen and checkpointed. It remains open only as historical documentation and for narrowly scoped correction work where necessary.

See:
- [`docs/V0.4_OVERVIEW.md`](docs/V0.4_OVERVIEW.md)
- [`docs/V0.4_CHECKPOINT.md`](docs/V0.4_CHECKPOINT.md)
- [`docs/V0.4_RELEASE_CHECKPOINT.md`](docs/V0.4_RELEASE_CHECKPOINT.md)

### v0.5

The active v0.5 development line is about **evidence strength**, moving from deterministic semantic simulation toward hardware-in-the-loop and then real Robot A → Robot B validation.

The simulation fixture is useful because it exercises the exact WHY / HOW / LOOKS split that later hardware experiments must preserve, while making the evidence boundary impossible to confuse with physical validation.

See:
- [`docs/V0.5_DEVELOPMENT_LINE.md`](docs/V0.5_DEVELOPMENT_LINE.md)
- [`docs/V0.5_SIMULATION_REFERENCE.md`](docs/V0.5_SIMULATION_REFERENCE.md)
- [`ROADMAP.md`](ROADMAP.md)

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
