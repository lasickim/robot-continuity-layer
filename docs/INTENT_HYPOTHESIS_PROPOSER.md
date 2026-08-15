# Intent Hypothesis Proposer Interface v0.1

## The idea in one sentence

> **Proposers may suggest the WHY. Evidence and explicit approval decide whether that WHY becomes continuity metadata.**

RCL already knows how to evaluate an engineering Intent hypothesis against observed context-action-outcome evidence. What was missing was a neutral way for different systems to *supply the hypothesis*.

The proposer interface fills that gap without making any model, vendor, or person authoritative.

## Mental model

```text
human reviewer
rule engine
LLM
VLM
other external model
        ↓
"Maybe this behavior exists for this reason."
        ↓
Intent Hypothesis Proposal Envelope
        ↓
actual observed evidence remains separate
        ↓
Intent Discovery
        ↓
Context Diagnostics
        ↓
explicit Intent Approval
```

A proposal is not an approved Intent.

## Why a neutral envelope matters

Different projects may use completely different hypothesis generators:

```text
Project A → human annotation
Project B → rules
Project C → language model
Project D → vision-language model
Project E → a future model RCL has never heard of
```

RCL should not need a different core implementation for each one.

All of them can instead produce the same semantic proposal artifact.

## Supported proposer kinds

v0.1 defines:

```text
human
rule_based
llm
vlm
external_model
other
```

`provider`, `model`, `tool`, and `version` metadata may be recorded for audit. They do not grant trust or authority.

## Proposal envelope

A proposal contains:

- proposer identity and kind;
- candidate action;
- context selector;
- outcome hypothesis;
- proposed engineering Intent;
- a concise rationale summary;
- evidence references;
- optional proposer self-confidence;
- deterministic proposal ID and SHA-256 binding;
- explicit non-authority flags.

The normative flags are:

```text
status = proposed
non_mutating = true
approved = false
```

## Self-confidence is not RCL confidence

A model may report:

```json
"self_confidence": 0.92
```

That means only:

> The proposer reports that it is confident in its own suggestion.

It does **not** mean:

```text
RCL confidence = 92%
```

RCL confidence still comes from the existing evidence evaluation path.

```text
Proposer self-confidence
→ audit metadata

Observed evidence
→ RCL Discovery confidence
```

A famous model, a larger model, or a higher self-confidence value receives no special approval power.

## No hidden reasoning contract

RCL does not require or store hidden chain-of-thought.

The interchange artifact carries only a concise, reviewable `rationale_summary`.

This is deliberate:

```text
reviewable hypothesis summary ✅
hidden internal reasoning transcript ❌
```

The schema uses `additionalProperties: false`, so undeclared fields such as a `chain_of_thought` payload are not part of the v0.1 contract.

## Proposal integrity

The proposal ID is deterministic over the proposal material.

```text
proposal material
        ↓
canonical JSON
        ↓
SHA-256
        ↓
intent-proposal-<16 hex chars>
```

If someone changes the rationale, model metadata, proposed Intent, evidence refs, self-confidence, or other bound material without rebuilding the proposal ID, validation fails.

The full proposal SHA-256 is also available for provenance records.

## Plugin contract

Third-party Python packages can implement the small `IntentHypothesisProposer` Protocol:

```python
from rcl.intent_proposer import IntentHypothesisProposer, ProposerMetadata

class MyProposer:
    @property
    def metadata(self) -> ProposerMetadata:
        ...

    def propose(self, request: dict) -> list[dict]:
        ...
```

The RCL runner validates every returned envelope as untrusted input and verifies that the envelope's proposer metadata matches the plugin's declared metadata.

A plugin cannot claim to be a human in metadata and then return an envelope attributed to a different model without the mismatch being detected.

## Reference proposer

`DeterministicReferenceProposer` exists only to exercise the plugin boundary in tests and examples.

It performs no external model inference.

RCL v0.1 deliberately includes no OpenAI, Anthropic, Google, Hugging Face, or other model-provider SDK dependency.

## Evidence remains separate

This separation is critical.

```text
Proposal
→ supplies the hypothesis

Evidence
→ supplies observations
```

The raw conversion helper requires caller-supplied episodes:

```python
proposal_to_raw_discovery_dataset(
    proposal,
    dataset_id="...",
    episodes=observed_episodes,
)
```

Those episodes are copied; RCL does not invent new ones.

For compacted evidence:

```python
proposal_to_summary_hypothesis(proposal, dataset_id="...")
```

returns only hypothesis metadata. It does not generate episode counts, means, action strata, or other aggregate evidence.

## Capability paths

The proposer envelope supports both current Intent forms:

```text
required_capabilities
```

or:

```text
capability_paths
```

The raw and summary Intent Discovery input schemas were aligned with the same rule so modern alternative capability paths can pass through the proposer → discovery pipeline without flattening them.

## CLI inspection

```bash
rcl inspect-intent-proposal examples/intent-proposer/llm-object-release.proposal.json
```

The human-readable output deliberately surfaces the authority boundary:

```text
Proposer Self-Confidence: 0.920 (NON-NORMATIVE)
RCL Confidence Evaluated: NO
Approved: NO
Profile Mutation: NO
```

JSON inspection is available with:

```bash
rcl inspect-intent-proposal PROPOSAL --json
```

## Reference fixtures

```text
examples/intent-proposer/human-object-release.proposal.json
examples/intent-proposer/rule-object-release.proposal.json
examples/intent-proposer/llm-object-release.proposal.json
examples/intent-proposer/vlm-object-release.proposal.json
```

They intentionally propose the same semantic WHY through different proposer types.

The point is that RCL treats the envelope contract consistently regardless of who generated it.

## Security and epistemic boundary

Intent Hypothesis Proposer v0.1 does not:

- call an LLM or VLM;
- prescribe a prompt;
- expose or require hidden chain-of-thought;
- trust a provider or model name;
- convert proposer self-confidence into RCL confidence;
- fabricate observed evidence;
- establish causality;
- establish subjective motivation;
- approve Intent;
- modify an RCL profile;
- certify physical safety.

It standardizes one narrow thing:

> **How an external system may submit a reviewable WHY hypothesis to RCL without gaining authority over the robot's continuity record.**
