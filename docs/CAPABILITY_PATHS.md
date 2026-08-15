# Alternative Capability Sets / Goal Satisfaction Paths v0.1

RCL Behavior Intent preserves **why** a behavior exists. Different robot bodies may satisfy the same goal through different semantic capability combinations.

> **Preserve the goal, not one body's capability recipe.**

A flat capability list is useful when every capability is always required, but it is too restrictive when several valid embodiment strategies exist.

## Scope

Capability Paths are declarative **semantic satisfiability metadata**. They describe which capability combinations are sufficient to represent a declared Intent on a target embodiment.

They are not:

- a planner DSL;
- a sensor wiring description;
- a ROS topic graph;
- a motor/controller command format;
- a ranking of camera, lidar, contact, network, or other technologies;
- evidence that the goal was actually achieved during execution.

Observed achievement remains the separate **Observed Intent Success** layer.

## Backward compatibility

Existing Intent remains valid:

```json
{
  "goal_id": "safety.verify_sitting_area_clear",
  "trigger": "activity.before_sit_down",
  "success_condition": "state.sitting_area_clear",
  "failure_action": "block",
  "criticality": "required",
  "required_capabilities": [
    "perception.sitting_area_clearance"
  ]
}
```

RCL normalizes this as one implicit path:

```json
{
  "path_id": "legacy.required_capabilities",
  "all_of": [
    "perception.sitting_area_clearance"
  ]
}
```

No existing profile needs to be rewritten merely to gain compatibility with the new evaluator.

v0.1 requires an Intent to declare **exactly one** of:

```text
required_capabilities
OR
capability_paths
```

Declaring both is rejected because the combined meaning would be ambiguous.

## New capability-path form

A new Intent can declare several named alternatives:

```json
{
  "goal_id": "safety.verify_sitting_area_clear",
  "trigger": "activity.before_sit_down",
  "success_condition": "state.sitting_area_clear",
  "failure_action": "block",
  "criticality": "required",
  "capability_paths": [
    {
      "path_id": "direct_clearance",
      "all_of": [
        "perception.sitting_area_clearance"
      ]
    },
    {
      "path_id": "rear_attention_classifier",
      "all_of": [
        "perception.directional_attention"
      ],
      "any_of": [
        "x.demo.rear_clearance_classifier",
        "x.demo.rear_occupancy_estimator"
      ]
    },
    {
      "path_id": "external_seat_state",
      "one_of": [
        "x.demo.external_seat_clearance",
        "x.demo.networked_seat_clearance"
      ]
    }
  ]
}
```

The `x.demo.*` identifiers above are deliberately extension capabilities. RCL does not standardize a hardware sensor name merely because one reference robot happens to use it.

## Boolean semantics

### Inside one path: clauses are AND

For:

```json
{
  "path_id": "rear_attention_classifier",
  "all_of": ["perception.directional_attention"],
  "any_of": [
    "x.demo.rear_clearance_classifier",
    "x.demo.rear_occupancy_estimator"
  ]
}
```

the target must satisfy:

```text
perception.directional_attention
AND
(
  x.demo.rear_clearance_classifier
  OR
  x.demo.rear_occupancy_estimator
)
```

### Across paths: paths are OR

For three declared paths:

```text
direct_clearance
OR
rear_attention_classifier
OR
external_seat_state
```

satisfying any complete path is enough to satisfy the Intent capability requirement.

## Clause definitions

### `all_of`

Every listed capability is required together.

```json
{"all_of": ["a", "b"]}
```

means:

```text
a AND b
```

### `any_of`

At least one listed capability must be available. The evaluator selects one deterministic matched capability for the path result.

```json
{"any_of": ["a", "b", "c"]}
```

means:

```text
a OR b OR c
```

### `one_of`

`one_of` means **select one valid capability to realize this clause**.

It does **not** mean the robot must physically expose exactly one of the listed options.

A target that has both `a` and `b` is not penalized for being more capable. The evaluator records both as matched and deterministically selects one for the realized path.

```json
{"one_of": ["a", "b"]}
```

means:

```text
select one from the available valid options
```

not Boolean XOR over the target's complete capability inventory.

## Deterministic evaluation

Public APIs:

```python
validate_intent_capability_paths(intent)
normalized_intent_capability_paths(intent)
declared_intent_capabilities(intent)
evaluate_intent_capability_paths(intent, available_capabilities)
select_satisfied_capability_path(
    intent,
    available_capabilities,
    preferred_path_ids=None,
)
```

Each path result contains:

```text
path_id
satisfied
selected_capabilities
clauses[]
reason
```

Each clause result contains:

```text
clause
options
matched
missing
selected
satisfied
```

This makes failure diagnostics explicit instead of flattening all alternatives into one misleading union of missing capabilities.

## Embodiment-specific path preference

RCL deliberately does not define one globally best path.

An adapter may provide an embodiment-specific preference order through:

```python
preferred_intent_capability_paths(...)
```

For example, a target that already exposes a direct semantic clearance state may prefer `direct_clearance`, while another target may prefer an external seat-state path.

If an adapter provides no preference, declaration order is the deterministic fallback. Declaration order is not a normative technology ranking.

## Migration report

`IntentMigrationResult` now reports:

```text
selected_capability_path_id
capability_path_results[]
```

Example successful result:

```json
{
  "goal_id": "safety.verify_sitting_area_clear",
  "status": "preserved",
  "target_strategy": "target.external_seat_clearance",
  "selected_capability_path_id": "external_seat_state",
  "required_capabilities": [
    "x.demo.external_seat_clearance"
  ],
  "missing_capabilities": [],
  "capability_path_results": [
    "... per-path diagnostics ..."
  ]
}
```

If no path is satisfied, `selected_capability_path_id` is `null` and every attempted path retains its own missing-clause diagnostics.

A `required` Intent still hard-fails migration only when no valid capability path can satisfy the goal, or when another higher-priority safety rule blocks it.

## Existing adapter compatibility

Third-party adapters that still construct an `IntentMigrationResult` using the historical flat `required_capabilities` fields do not need an immediate source rewrite.

When no explicit capability-path result is supplied, RCL backfills the result as:

```text
legacy.required_capabilities
```

with one `all_of` clause.

Adapters that want to consume new `capability_paths` must use the path-aware evaluator rather than treating the union of all declared capabilities as simultaneously required.

## Capability vocabulary boundary

Capability Paths should use semantic capability identifiers.

Good:

```text
perception.sitting_area_clearance
perception.directional_attention
x.vendor.semantic_clearance_estimator
```

Avoid encoding portable requirements such as:

```text
camera_model_X
lidar_topic_/scan
GPIO17
vendor_controller_command_42
```

Those belong in the embodiment adapter or vendor integration layer.

## Reference examples

Intent snippet:

```text
examples/capability-paths/pre-sit-intent.json
```

Three different target bodies:

```text
examples/capability-paths/target-direct.embodiment.json
examples/capability-paths/target-rear-attention.embodiment.json
examples/capability-paths/target-external.embodiment.json
```

Reference adapter:

```text
rcl.capability_path_reference_adapter.CapabilityPathReferenceAdapter
```

They demonstrate the same pre-sit clearance goal being represented through different capability paths and different target-native strategies.

## Safety and epistemic boundary

Capability-path satisfaction means:

> The target declares enough semantic capability to represent at least one valid route to the engineering goal.

It does not mean:

- the target actually succeeded during a physical trial;
- the selected route is universally safer or better;
- a safety interlock may be bypassed;
- a visible legacy expression should be deleted;
- the robot subjectively understands the goal.

Safety still outranks continuity, and **Observed Intent Success** remains the separate evidence layer for actual observed goal satisfaction.
