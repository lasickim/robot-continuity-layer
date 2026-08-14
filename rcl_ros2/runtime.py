from __future__ import annotations

from typing import Any


class TwistPublisher:
    """Small optional runtime bridge for ROS 2 ``geometry_msgs/msg/Twist``.

    Importing this module does not require ROS 2. ROS message imports happen
    only when an instance is created, which keeps the RCL core and unit tests
    usable on non-ROS systems.
    """

    def __init__(
        self,
        node: Any,
        *,
        topic: str = "/cmd_vel",
        qos_depth: int = 10,
    ) -> None:
        if not topic:
            raise ValueError("topic must not be empty")
        if qos_depth <= 0:
            raise ValueError("qos_depth must be positive")

        try:
            from geometry_msgs.msg import Twist
        except ImportError as exc:  # pragma: no cover - depends on ROS install
            raise RuntimeError(
                "ROS 2 geometry_msgs is not available. Source a ROS 2 "
                "environment before constructing TwistPublisher."
            ) from exc

        self._twist_type = Twist
        self._publisher = node.create_publisher(Twist, topic, qos_depth)

    def publish_velocity(self, *, linear_x: float, angular_z: float) -> None:
        message = self._twist_type()
        message.linear.x = float(linear_x)
        message.angular.z = float(angular_z)
        self._publisher.publish(message)
