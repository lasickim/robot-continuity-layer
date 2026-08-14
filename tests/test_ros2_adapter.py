from rcl_ros2 import ROS2MobileBaseAdapter


SOURCE = {
    "embodiment_id": "source-a",
    "class": "mobile_base",
    "capabilities": [
        "navigation.planar_velocity",
        "perception.person_tracking",
        "perception.directional_attention",
    ],
    "limits": {
        "max_linear_speed_mps": 0.8,
        "max_angular_speed_rps": 1.0,
    },
}

TARGET = {
    "embodiment_id": "ros2-target",
    "class": "mobile_base",
    "capabilities": [
        "navigation.planar_velocity",
        "perception.person_tracking",
        "perception.forward_range",
    ],
    "limits": {
        "max_linear_speed_mps": 1.2,
        "max_angular_speed_rps": 1.4,
    },
}


def test_follow_person_maps_to_ros2_twist_plan() -> None:
    adapter = ROS2MobileBaseAdapter()
    behavior = {
        "behavior_id": "navigation.follow_person",
        "required_capabilities": [
            "navigation.planar_velocity",
            "perception.person_tracking",
        ],
        "parameters": {
            "preferred_distance_m": 1.4,
            "speed_style": "gentle",
            "turn_style": "cautious",
            "stop_delay_ms": 350,
        },
    }

    result = adapter.translate_behavior(behavior, SOURCE, TARGET)

    assert adapter.supports(TARGET)
    assert result.status == "preserved"
    assert result.similarity == 1.0
    assert result.mapped_parameters["following_distance_m"] == 1.4
    assert result.mapped_parameters["linear_speed_limit_mps"] == 0.42
    assert result.mapped_parameters["angular_speed_limit_rps"] == 0.63
    assert result.mapped_parameters["execution"]["ros2_interface"] == {
        "transport": "topic",
        "topic": "/cmd_vel",
        "message_type": "geometry_msgs/msg/Twist",
        "control_rate_hz": 10.0,
    }


def test_pre_turn_behavior_is_honestly_approximated() -> None:
    adapter = ROS2MobileBaseAdapter()
    behavior = {
        "behavior_id": "navigation.pre_turn_observation",
        "required_capabilities": ["perception.directional_attention"],
        "parameters": {
            "minimum_turn_deg": 70,
            "observation_pause_ms": 250,
        },
    }

    result = adapter.translate_behavior(behavior, SOURCE, TARGET)

    assert result.status == "approximated"
    assert result.similarity == 0.65
    assert result.missing_capabilities == ("perception.directional_attention",)
    assert result.mapped_parameters["execution"]["controller"] == "base_yaw_preview"


def test_missing_person_tracking_is_unsupported() -> None:
    adapter = ROS2MobileBaseAdapter()
    target = {
        **TARGET,
        "capabilities": ["navigation.planar_velocity", "perception.forward_range"],
    }
    behavior = {
        "behavior_id": "navigation.follow_person",
        "parameters": {"speed_style": "normal"},
    }

    result = adapter.translate_behavior(behavior, SOURCE, target)

    assert result.status == "unsupported"
    assert result.similarity == 0.0
    assert "perception.person_tracking" in result.missing_capabilities
