# ROS 2 Reference Adapter

**Status:** experimental v0.3-dev integration

The ROS 2 reference adapter demonstrates how portable RCL semantics can be translated into a ROS-facing execution plan without making ROS-specific commands part of the core RCL profile.

The first reference target is **ROS 2 Lyrical Luth** and a planar mobile base using `geometry_msgs/msg/Twist` for velocity commands.

## Boundary

```text
portable .rcl profile
        ↓
ROS2MobileBaseAdapter
        ↓
ROS-facing execution plan
        ↓
TwistPublisher / robot controller
        ↓
physical or simulated mobile base
```

The portable profile should describe meaning such as `gentle` following behavior or preferred distance. Topic names, ROS message types, QoS, and controller implementation belong to the integration layer.

## Example

```python
from rcl_ros2 import ROS2MobileBaseAdapter

adapter = ROS2MobileBaseAdapter(
    cmd_vel_topic="/cmd_vel",
    control_rate_hz=10.0,
)

result = adapter.translate_behavior(
    behavior,
    source_embodiment,
    target_embodiment,
)

print(result.status)
print(result.mapped_parameters["execution"])
```

A preserved person-following behavior produces an execution plan containing a ROS 2 topic interface and target-relative velocity limits. For example, the semantic speed style `gentle` is mapped relative to the target embodiment's declared maximum velocity rather than copying a source motor percentage.

## Runtime bridge

`rcl_ros2.runtime.TwistPublisher` is deliberately tiny. It accepts an existing ROS 2 node and publishes `geometry_msgs/msg/Twist` messages:

```python
from rcl_ros2 import TwistPublisher

publisher = TwistPublisher(node, topic="/cmd_vel")
publisher.publish_velocity(linear_x=0.2, angular_z=0.0)
```

ROS imports are delayed until `TwistPublisher` is constructed, so the core package and adapter unit tests can run on systems without ROS installed.

## Reference target

See:

```text
examples/targets/ros2-lyrical-mobile-base.embodiment.json
```

The target intentionally lacks `perception.directional_attention`. Therefore the existing legacy `navigation.pre_turn_observation` behavior is reported as an **approximation**, using a small base-yaw preview when planar velocity and forward-range sensing are available.

This demonstrates a central RCL rule: an adapter must report semantic degradation rather than silently claiming exact preservation.

## What this adapter does not provide

The initial reference adapter does not implement a person tracker, Nav2 behavior tree, localization stack, safety controller, or robot-specific motor driver. Those are intentionally outside RCL's portable continuity layer.

A real deployment is expected to connect the execution plan to an existing perception and control stack.

## Tests

The adapter tests do not require ROS 2 or physical hardware:

```bash
pytest -q tests/test_ros2_adapter.py
```

A later real-robot milestone will add measured before/after behavior evaluation in addition to configuration-level semantic migration.
