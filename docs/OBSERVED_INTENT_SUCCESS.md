# Observed Intent Success v0.1

Observed Intent Success asks a different question from motion similarity:

> Did the observed robot actually satisfy the declared engineering success condition for this behavior intent?

It is intentionally body-independent. A target robot may use a completely different physical strategy from the source robot and still pass if the same declared success condition is observed.

## Example

```text
Robot V1
  strategy: rearward body observation
  visible motion: turns/checks behind
  success_condition: state.sitting_area_clear
  observed result: satisfied
  => PASS

Robot V2
  strategy: direct rear depth sensing
  visible motion: no turn required
  success_condition: state.sitting_area_clear
  observed result: satisfied
  => PASS
```

Low motion similarity does not imply failed intent preservation.

## Input

`Intent Observation Input v0.1` records one controlled observation per behavior:

```json
{
  "intent_observation_version": "0.1",
  "robot_id": "RCL-INTENT-DEMO-V2",
  "embodiment_id": "intent-demo-v2-humanoid",
  "captured_at": "2026-08-15T01:05:00Z",
  "intent_observations": [
    {
      "observation_id": "v2-sit-001",
      "behavior_id": "safety.pre_sit_clearance_check",
      "trigger": "activity.before_sit_down",
      "trigger_state": "observed",
      "success_condition": "state.sitting_area_clear",
      "success_state": "satisfied",
      "strategy_id": "target.direct_rear_depth_sensing",
      "evidence_refs": ["observation://v2/sit/rear-depth"]
    }
  ]
}
```

`strategy_id` is informational audit metadata. It never affects pass/fail logic.

## Per-intent statuses

```text
pass
  declared trigger was observed and the declared success condition was satisfied

fail
  declared trigger was observed and the declared success condition was not satisfied

not_observable
  the success condition could not be observed, or the required behavior observation is missing

not_triggered
  the declared trigger did not occur during the controlled observation
```

The observation's `behavior_id`, `trigger`, and `success_condition` must exactly match the declared `behavior.intent` metadata. RCL will not silently remap one semantic condition to another.

If `trigger_state=not_observed`, `success_state` must be `not_observable`. RCL does not allow success to be claimed for an intent whose declared trigger was not observed.

## Overall report status

Criticality controls only the aggregate blocking rule:

```text
required + fail
  => overall failed

required + not_observable/not_triggered/missing
  => overall inconclusive

preferred/advisory + non-pass
  => recorded in nonblocking_failures
     but does not fail the overall report
```

No universal success-rate threshold is introduced in v0.1. This is a controlled single-observation evaluation profile, not repeated statistical intent-success evaluation.

## CLI

```bash
rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json
```

JSON output:

```bash
rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json \
  --json
```

Write a machine-readable report:

```bash
rcl evaluate-intent \
  examples/intent/sit-assistant-v1 \
  examples/intent-observations/sit-assistant-v2.observations.json \
  --output intent-success-report.json
```

Exit codes:

```text
0  passed
7  inconclusive
8  failed
2  input / validation error
```

## What this does not mean

Observed Intent Success v0.1 does not:

- measure consciousness or subjective motivation;
- prove causal truth;
- require the source-body motion or visible expression;
- certify physical safety;
- define a universal statistical acceptance threshold;
- replace repeated-trial or repeated-session evaluation.

It is a narrow engineering observation: whether a declared semantic success condition was observed during a controlled execution.
