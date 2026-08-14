# RCL Capability Registry v0.1

**Status:** Experimental · RCL v0.3-dev

The RCL Capability Registry defines stable semantic names for abilities that an embodiment or adapter can declare and require.

Its purpose is interoperability. Two implementations should not describe the same ability using unrelated names such as `human_detect`, `person_track`, and `vision.person` and then expect automatic migration to understand that they mean the same thing.

The machine-readable registry is published at:

```text
rcl/data/capability-registry-v0.1.json
```

The registry schema is published at:

```text
rcl/schemas/capability-registry.schema.json
```

## Capability IDs describe ability, not implementation

A capability ID describes **what the target can semantically provide**, not how it provides it.

For example:

```text
navigation.planar_velocity
```

may be implemented through ROS 2 `geometry_msgs/msg/Twist`, a vendor SDK, CAN messages, wheel-speed controllers, a learned policy, or another mechanism.

Those execution details belong in the embodiment adapter, not in the portable capability ID.

## Standard capability syntax

Registered standard capabilities use:

```text
<reserved_namespace>.<semantic_path>
```

Examples:

```text
navigation.planar_velocity
perception.person_tracking
perception.forward_range
perception.directional_attention
```

Segments use lowercase ASCII letters, digits, and underscores and begin with a letter.

A capability inside a reserved namespace is valid as a portable RCL standard capability **only when it appears in the published registry**.

Therefore:

```text
perception.person_tracking     VALID — registered
perception.telepathy           INVALID — reserved but unregistered
```

This prevents two projects from independently assigning different meanings to the same standard-looking name.

## Reserved namespaces

Capability Registry v0.1 reserves these top-level namespaces:

| Namespace | Intended domain |
|---|---|
| `navigation` | Goal, path, and motion-execution capabilities for moving through an environment |
| `perception` | Sensing, estimation, recognition, and tracking of the environment and relevant entities |
| `manipulation` | Object, tool, load, contact, grasp, and force interaction |
| `interaction` | Intentional human-robot and robot-robot communication and interaction |
| `mobility` | Embodiment-level locomotion and posture abilities |
| `safety` | Protective functions, safety states, limits, and safety-relevant capabilities |
| `system` | Lifecycle, diagnostics, power, compute, and robot-system functions |

A reserved namespace is **not** a claim that every future capability within that namespace has already been standardized.

## Extension capabilities

Third parties do not need registry approval to experiment.

Vendor, research, or experimental capabilities use:

```text
x.<owner>.<semantic_path>
```

Examples:

```text
x.acme.stereo_person_tracking
x.example_lab.social_distance_estimator
x.vendor42.custom_gripper_mode
```

The `owner` segment identifies the organization or project responsible for the extension semantics.

Extension capabilities:

- are syntactically valid RCL capability references;
- may appear in profiles and embodiments where extensions are allowed;
- do not claim RCL standard semantics;
- must not be silently renamed into a standard capability;
- can later be proposed as standard capabilities through the normal registry process.

A project should document the semantics of every extension capability it publishes.

## Initial registered capabilities

### `navigation.planar_velocity`

The target can realize bounded planar translational and yaw velocity for semantic mobile-base execution.

It does **not** imply global localization, route planning, obstacle avoidance, a ROS topic, or any particular motor/controller architecture.

### `perception.person_tracking`

The target can maintain a temporally coherent person reference sufficient for closed-loop behavior such as following or approach regulation.

A single-frame person detector alone does not necessarily satisfy this capability.

It does not require face recognition, biometric identity, or any specific perception model.

### `perception.forward_range`

The target can estimate obstacle or free-space range representative of its forward travel region.

The sensing mechanism is intentionally unspecified and may use lidar, depth, ToF, ultrasonic sensing, fused perception, or another suitable implementation.

### `perception.directional_attention`

The target can intentionally direct or select effective sensing toward a requested direction.

This can be implemented using a movable sensor, head, gimbal, crop, attention policy, sensor selection, or other mechanism. Human-like gaze is not required.

## Validation behavior

RCL classifies capability IDs into four practically important groups:

```text
standard          registered portable RCL capability
extension         valid x.<owner>.* capability
unknown_reserved  standard-looking ID not present in the registry
invalid           malformed or unreserved portable ID
```

Python:

```python
from rcl import classify_capability_id, validate_capability_id

print(classify_capability_id("perception.person_tracking"))
validate_capability_id("x.acme.stereo_person_tracking")
```

CLI:

```bash
rcl capabilities list
rcl capabilities show perception.person_tracking
rcl capabilities validate perception.person_tracking
rcl capabilities validate x.acme.stereo_person_tracking
```

Machine-readable output is available with `--json`.

## Conformance behavior

The v0.3 migration path validates:

- source embodiment capabilities;
- target embodiment capabilities;
- the complete required capability set declared by an adapter for each behavior.

An adapter that introduces an unknown capability inside a reserved namespace cannot pass the migration conformance path merely by using a standard-looking name.

Extension capabilities remain permitted so independent implementations can evolve without central coordination.

## Registry evolution

Capability Registry versions are independent from individual adapter versions.

For the v0.x series:

1. Existing registered IDs should not change meaning silently.
2. New standard IDs should include explicit semantics and non-goals.
3. If semantics must materially change, a new capability ID should be preferred over redefining the old one.
4. Deprecated capabilities should remain identifiable and may declare a `replaced_by` capability.
5. Proposals should include at least one concrete interoperability use case.

The initial registry is intentionally small. RCL should add capabilities because real adapters need a shared semantic contract, not because a large taxonomy looks complete on paper.
