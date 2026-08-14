# Intent Discovery / Intent Candidate v0.1

Intent Discovery is the bridge between **a newly observed behavioral pattern** and **a declared Behavior Intent**.

It does not autonomously decide what a robot "really meant." Instead, it evaluates whether a proposed goal hypothesis is supported by repeated context-action-outcome observations strongly enough to deserve review.

```text
experience
    ↓
repeated action pattern
    ↓
proposed goal hypothesis
    ↓
context-action-outcome evidence
    ↓
Intent Candidate
    ↓
explicit review / future approval
    ↓
declared Behavior Intent
```

## Why this layer exists

Behavior Intent v0.1 can already preserve a declared purpose such as:

```text
safety.verify_sitting_area_clear
```

But real robots can learn behaviors that the RCL authors never anticipated.

A robot may, for example, begin holding an object for a few hundred milliseconds after release because that pattern reduces object instability. RCL should not require a developer to add:

```python
if action == "post_release_hold":
    goal = "stabilize_released_object"
```

for every future learned behavior.

Intent Discovery therefore uses a generic evidence format.

## Model boundary

v0.1 intentionally separates **hypothesis proposal** from **evidence evaluation**.

```text
learning system / LLM / VLM / human
        ↓
proposed goal hypothesis
        ↓
RCL deterministic evidence engine
```

The core engine does not use an LLM and does not invent goal text.

A future model plugin may propose:

```text
goal_id
trigger
success condition
failure action
required capabilities
```

but the RCL evidence engine remains model-independent.

## Dataset

A dataset declares:

- one candidate action;
- one context selector;
- one target outcome;
- one proposed intent;
- repeated episodes.

Example:

```json
{
  "discovery_dataset_version": "0.1",
  "dataset_id": "demo-object-release-stability-001",
  "candidate_action_id": "interaction.post_release_hold",
  "context_match": {
    "task": "object_release"
  },
  "outcome": {
    "outcome_id": "object_stability_score",
    "type": "numeric",
    "higher_is_better": true,
    "minimum_meaningful_effect": 0.15,
    "unit": "ratio"
  },
  "proposed_intent": {
    "goal_id": "x.rcl-demo.stabilize_released_object",
    "trigger": "activity.after_object_release",
    "success_condition": "state.released_object_stable",
    "failure_action": "retry",
    "criticality": "preferred",
    "required_capabilities": [
      "x.rcl-demo.object_stability_observation"
    ]
  }
}
```

Raw private audio, video, images, face data, and unrestricted conversation history are outside this format.

## Episode model

Each episode records semantic context, whether the candidate action happened, and the measured outcome.

```json
{
  "episode_id": "release-01",
  "context": {
    "task": "object_release",
    "surface": "table"
  },
  "action": {
    "action_id": "interaction.post_release_hold",
    "performed": true,
    "parameters": {
      "hold_ms": 390
    }
  },
  "outcomes": {
    "object_stability_score": 0.96
  }
}
```

The action parameters are descriptive evidence. v0.1 does not infer a canonical motor command from them.

## Evidence calculation

Only episodes matching every key/value in `context_match` are scored.

For those episodes:

```text
Ncontext  = matching episodes
Npresent  = episodes where candidate action occurred
Nabsent   = episodes where it did not occur
repeat    = Npresent / Ncontext
```

For a numeric outcome:

```text
mean_present = mean(outcome | action present)
mean_absent  = mean(outcome | action absent)
raw_diff     = mean_present - mean_absent
```

For a binary outcome, `true=1` and `false=0`, so the means are success rates.

The beneficial effect is:

```text
higher_is_better = true
    beneficial_effect = raw_diff

higher_is_better = false
    beneficial_effect = -raw_diff
```

The dataset, not RCL, declares `minimum_meaningful_effect` because different outcomes have different units and practical scales.

## Default policy

Published at:

```text
spec/policies/intent-discovery-policy-v0.1.json
```

Default gates:

```text
context episodes       >= 10
action-present samples >= 4
action-absent samples  >= 4
action repeat rate     >= 0.30
beneficial effect      >= dataset minimum_meaningful_effect
```

Every gate must pass for `status=candidate`.

Otherwise:

```text
status=insufficient_evidence
recommended_next_action=collect_more_evidence
```

## Confidence labels

`confidence` is an **evidence-strength label**, not a probability that the proposed intent is true.

`moderate` means all candidate gates passed.

`strong` additionally requires the sample gates and beneficial effect to exceed the default thresholds by the configured strong-evidence multipliers.

The default multipliers are `2.0`.

This must not be interpreted as:

```text
strong = 95% chance the inferred goal is correct
```

No such probability is estimated by v0.1.

## Association is not causality

A candidate report always contains:

```json
{
  "causal_claim": false
}
```

An observed association can have alternative explanations:

- another hidden state may cause both the action and the outcome;
- the robot may choose the action only in easier situations;
- sensor or operator behavior may change between groups;
- the proposed semantic goal may simply be wrong.

Intent Discovery v0.1 therefore produces a **reviewable hypothesis**, not causal proof.

## CLI

Object-release numeric example:

```bash
rcl discover-intent \
  examples/intent-discovery/object-release-stability.dataset.json
```

Unrelated binary auto-docking example:

```bash
rcl discover-intent \
  examples/intent-discovery/dock-alignment.dataset.json
```

JSON:

```bash
rcl discover-intent dataset.json --json
```

Custom policy:

```bash
rcl discover-intent dataset.json --policy custom-policy.json --json
```

Exit codes:

```text
0  candidate
7  insufficient_evidence
2  validation / input error
```

## Example output

```text
RCL Intent Discovery
Dataset: demo-object-release-stability-001
Action: interaction.post_release_hold
Proposed Goal: x.rcl-demo.stabilize_released_object
Samples: context=20 present=10 absent=10 ignored=2
Action Repeat Rate: 0.500
Status: candidate
Confidence: strong
Causal Claim: NO
Next: review_candidate
```

## No automatic profile mutation

Intent Discovery does not accept an RCL profile as a mutation target.

It cannot write:

```text
behavior.intent
```

and it cannot silently promote a hypothesis into a portable goal.

A later explicit Intent Approval step should convert an accepted candidate into a new immutable profile snapshot, following the same design principle used by Habit Approval.

## Future proposer layer

A future proposer may use:

- deterministic causal-feature rules;
- an LLM;
- a VLM;
- a robot foundation model;
- a human annotation interface.

That proposer should remain above the RCL evidence engine.

```text
proposer
   ↓
Intent Discovery Dataset
   ↓
RCL evidence engine
   ↓
Intent Candidate Report
```

This keeps RCL portable across AI models and vendors.

## Scope boundary

Intent Discovery v0.1 does not define consciousness, subjective purpose, free will, causal identification, or human-like understanding. It reports whether declared observations provide enough transparent engineering evidence to review a proposed semantic goal.
