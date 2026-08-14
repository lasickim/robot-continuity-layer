# Experiment Context and Measurement Protocol v0.1

Repeated-trial continuity is only meaningful when Robot A and Robot B are measured under declared comparable conditions. RCL therefore places a context gate in front of Statistical Continuity Evaluation.

## Trial capture version

Repeated-trial input is now `trial_observation_version: 0.2` and contains an `experiment` object with a shared protocol and session-specific context.

```json
{
  "experiment": {
    "protocol": {
      "protocol_id": "rcl.person_following.baseline",
      "protocol_version": "0.1",
      "comparison_fields": [
        "task_id",
        "environment_id",
        "subject_ref",
        "start_condition_id"
      ]
    },
    "context": {
      "session_id": "robot-a-session-001",
      "task_id": "follow-person-straight-5m",
      "environment_id": "demo-lab-a-layout-01",
      "subject_ref": "subject-demo-01",
      "start_condition_id": "stationary-2m-behind-subject",
      "software_ref": "controller@1.0",
      "adapter_ref": "adapter@1.0",
      "sensor_config_ref": "sensor-set@1"
    }
  }
}
```

## Strict comparison fields

The protocol selects which context fields must match. If `comparison_fields` is omitted, the safe default is:

```text
task_id
environment_id
start_condition_id
```

Available strict fields are:

```text
task_id
environment_id
subject_ref
operator_ref
start_condition_id
```

A person-following protocol should normally add `subject_ref`; another task may not need it.

## Informational robot metadata

These values are recorded but are not strict comparison keys unless future protocol versions define otherwise:

```text
software_ref
adapter_ref
sensor_config_ref
notes
```

This is deliberate. Robot A and Robot B may use different software, adapters, sensors, and hardware while being tested under the same external scenario.

## Context gate

Before Wasserstein scoring, RCL compares:

1. protocol ID,
2. protocol version,
3. protocol comparison-field list,
4. every selected context value.

If any required comparison differs or is missing:

```text
Context Comparable: NO
Statistical Continuity Score: N/A
Status: context_mismatch
```

No behavior distribution score is calculated. This prevents environmental differences from being silently interpreted as robot continuity differences.

## Machine-readable report

`statistical-continuity-report` now includes `context_comparison` with:

- `compatible`
- source/target protocol references
- comparison fields
- blocking mismatches
- non-blocking informational differences

When context is incompatible, `score` is `null` and `metric_results` is empty.

## Reference protocol

See `examples/protocols/person-following-baseline.protocol.json` and the Robot A/B trial fixtures in `examples/trials/`.

## Scope boundary

RCL checks declared metadata. Matching IDs do not prove that two rooms, subjects, starting poses, sensors, or measurements were physically identical. Formal metrology, calibrated instrumentation, randomization, blinding, and laboratory quality systems remain outside this v0.1 layer.
