# Changelog

## 0.3.0-dev — 2026-08-14

- Added the first ROS 2 reference integration as a separate `rcl_ros2` package.
- Added `ROS2MobileBaseAdapter` for semantic mobile-base migration plans.
- Added a lazy `geometry_msgs/msg/Twist` runtime publisher bridge.
- Added a ROS 2 Lyrical mobile-base target embodiment example.
- Added unit tests that validate ROS-facing migration behavior without requiring ROS 2 or physical hardware.
- Added public compatibility levels, contribution guidance, issue templates, and pull request guidance.
- Expanded the public roadmap toward adapter conformance and real-robot evaluation.

## 0.2.0-dev — 2026-08-14

- Added explicit `RCLAdapter` interface.
- Added semantic capability matching.
- Added behavior migration statuses: preserved, approximated, unsupported, blocked_for_safety.
- Added machine-readable migration report schema.
- Added Behavior Continuity Score v0.2.
- Added rule that required behavior failures force `migration_success=false` regardless of score.
- Added Robot A → Robot B reference adapter and target embodiment.
- Added `rcl migrate` and `rcl report` commands.
- Packaged JSON schemas with the Python package so installed builds can validate profiles.
- Hardened `.rcl` loading to reject unexpected archive entries.

## 0.1.0-dev — 2026-08-14

- Initial continuity profile draft.
- Added identity, preferences, behavior, skills, and embodiment payloads.
- Added ZIP-based `.rcl` package and SHA-256 manifest.
- Added basic CLI validation, pack, and inspect commands.
