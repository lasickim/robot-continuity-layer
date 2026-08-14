# Behavior Intent / Goal Semantics v0.1

Behavior Intent lets RCL preserve **why a behavior exists** separately from the source robot's physical strategy or recognizable motion.

The core separation is:

```text
WHY      -> intent
WHAT     -> semantic behavior + parameters
HOW      -> embodiment adapter / target strategy
LOOKS    -> expression
HISTORY  -> habit / legacy
```

This matters whenever a source robot's visible motion was originally caused by a hardware limitation.

## Example: looking behind before sitting

Robot V1 may turn its head or body before sitting because its original sensor arrangement cannot otherwise inspect the sitting area.

The portable functional goal is not:

```text
turn rearward before sitting
```

It is:

```text
verify the intended sitting area is clear before sitting
```

A v0.4 intent declaration can express that goal directly:

```json
{
  "behavior_id": "safety.pre_sit_clearance_check",
  "intent": {
    "goal_id": "safety.verify_sitting_area_clear",
    "trigger": "activity.before_sit_down",
    "success_condition": "state.sitting_area_clear",
    "failure_action": "block",
    "criticality": "required",
    "required_capabilities": [
      "perception.sitting_area_clearance"
    ]
  },
  "expression": {
    "expression_id": "observation.brief_rearward_check",
    "preservation_priority": "optional",
    "required_capabilities": [
      "perception.directional_attention"
    ]
  }
}
```

Robot V2 may have a rear depth camera and therefore satisfy the same intent without turning at all.

```text
V1
before_sit_down
    ↓
rearward observation
    ↓
verify sitting area clear
    ↓
sit

V2
before_sit_down
    ↓
direct rear clearance sensing
    ↓
verify sitting area clear
    ↓
sit
```

The target strategy changed, but the goal did not.

## Intent and expression are separate migration facets

A v0.4 migration result may therefore report:

```text
Behavior:   preserved
Intent:     preserved
Strategy:   direct_rear_clearance_sensing
Expression: unsupported
```

This is a valid continuity result when the expression is optional.

The old visible motion can still be retained as a historical/recognizable expression when the target embodiment can reproduce it, but the expression never substitutes for satisfying a required functional intent.

## Required intent is a hard gate

The existing Behavior Continuity Score remains behavior-similarity based in v0.4-dev. Intent is not folded into that numeric score yet.

Instead, a required intent acts as a hard migration gate:

```text
required intent preserved/approximated
    -> migration may succeed

required intent unsupported/blocked_for_safety
    -> migration_success = false
```

The report exposes the failure explicitly through `intent_required_failures`.

Optional/preferred expression loss does not by itself make migration fail.

## Example: wrist rotation before handover

Suppose Robot V1 rolls its wrist shortly before giving an object to a person.

Possible original reason:

```text
place the object in a handover-friendly orientation
```

The portable intent is therefore:

```json
{
  "intent": {
    "goal_id": "interaction.optimize_handover_orientation",
    "trigger": "interaction.before_handover_release",
    "success_condition": "state.handover_orientation_acceptable",
    "failure_action": "retry",
    "criticality": "preferred",
    "required_capabilities": [
      "manipulation.handover_orientation"
    ]
  },
  "expression": {
    "expression_id": "handover.brief_wrist_roll",
    "preservation_priority": "optional",
    "required_capabilities": [
      "x.demo.wrist_roll"
    ]
  }
}
```

Robot V2 might satisfy the same goal with different arm geometry, grasp selection, or wrist kinematics. It does not need to copy the source angle.

## Behavior Intent vocabulary v0.1

The machine-readable vocabulary is published at:

```text
spec/intent-vocabulary-v0.1.json
```

Packaged runtime copy:

```text
rcl/data/intent-vocabulary-v0.1.json
```

Initial standard goals:

```text
safety.verify_sitting_area_clear
interaction.optimize_handover_orientation
```

A registered goal defines allowed trigger IDs, success-condition IDs, and failure actions.

Unknown standard-looking goals are rejected. Experimental/vendor goals may use:

```text
x.<owner>.<semantic_path>
```

## Initial semantic capabilities

v0.4 adds:

```text
perception.sitting_area_clearance
manipulation.handover_orientation
```

These describe what a target can semantically accomplish, not which sensor, joint, controller, or middleware API it uses.

For example, `perception.sitting_area_clearance` explicitly does **not** imply that the robot has to turn its head or body.

## Fields

### `intent.goal_id`

Portable semantic purpose from the Behavior Intent vocabulary or an `x.<owner>.*` extension.

### `intent.trigger`

Semantic event that activates the goal.

### `intent.success_condition`

State that must be established before the goal is considered satisfied.

### `intent.failure_action`

One of:

```text
block
retry
request_help
abort
degrade_safely
```

The registered goal may allow only a subset.

### `intent.criticality`

```text
required
preferred
advisory
```

A required intent cannot silently disappear during migration.

### `intent.required_capabilities`

Semantic capabilities necessary to satisfy the goal. These should be body-independent where possible.

### `intent.constraints`

Optional semantic conditions that must remain true while attempting the goal.

### `expression`

Separately describes a recognizable visible behavior. Expression preservation is `preferred` or `optional` in v0.1 and is never treated as proof that the functional goal was satisfied.

## Profile Diff

`rcl diff` now includes intent and expression fields, including changes to:

```text
intent.goal_id
intent.trigger
intent.success_condition
intent.failure_action
intent.criticality
intent.required_capabilities
intent.constraints
expression.expression_id
expression.preservation_priority
expression.required_capabilities
```

This makes a change in **why the robot acts** visible instead of hiding it behind unchanged motion parameters.

## Reference fixture

Source profile:

```text
examples/intent/sit-assistant-v1
```

Target embodiment:

```text
examples/targets/intent-demo-v2.embodiment.json
```

Reference adapter:

```text
rcl.intent_reference_adapter.IntentReferenceAdapter
```

The V2 target deliberately provides the functional intent capabilities while omitting the V1 expression capabilities.

## Important boundary

Behavior Intent represents a declared engineering purpose, trigger, success condition, and failure policy.

It does **not** claim:

- consciousness;
- subjective motivation;
- free will;
- human-like understanding;
- that the robot internally reasons about purpose in natural language;
- physical safety certification.

RCL can preserve and translate declared goal semantics without making claims about machine phenomenology.
