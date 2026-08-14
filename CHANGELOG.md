# Changelog

## 0.3.0-dev — 2026-08-14

- Added the first ROS 2 reference integration as a separate `rcl_ros2` package.
- Added `ROS2MobileBaseAdapter` for semantic mobile-base migration plans.
- Added a lazy `geometry_msgs/msg/Twist` runtime publisher bridge.
- Added a ROS 2 Lyrical mobile-base target embodiment example.
- Added unit tests that validate ROS-facing migration behavior without requiring ROS 2 or physical hardware.
- Added public compatibility levels, contribution guidance, issue templates, and pull request guidance.
- Added the first executable adapter conformance suite: `rcl.adapter.mobile_base.v0.3`.
- Added `rcl-conformance test module.path:AdapterClass` with text and JSON output.
- Added a machine-readable conformance report schema.
- Added negative conformance tests that reject adapters which hide missing required capabilities.
- Added Capability Registry v0.1 with the initial standard capability vocabulary.
- Reserved `navigation`, `perception`, `manipulation`, `interaction`, `mobility`, `safety`, and `system` standard namespaces.
- Added the `x.<owner>.<semantic_path>` extension capability namespace.
- Added Python APIs for capability lookup, classification, and validation.
- Added `rcl capabilities list/show/validate` CLI commands.
- Added migration-time validation for source, target, and adapter-required capability IDs.
- Added conformance coverage that rejects unknown IDs inside reserved capability namespaces.
- Added optional numeric behavior evaluation metadata with parameter references, tolerance bands, weights, and required/optional observations.
- Added Observation Input v0.1 and a machine-readable Observed Continuity Evaluation Report v0.1.
- Added `evaluate_observed_continuity()` and `rcl evaluate` for observed-vs-declared behavior scoring.
- Added a transparent full-credit / linear-falloff / zero-credit numeric scoring rule.
- Added profile validation for invalid evaluation parameter references and invalid tolerance falloff ranges.
- Added a Robot B observation example (`1.37 m`, `372 ms`) and observed evaluation documentation.
- Added repeated-trial observation format v0.2 for source and target robots.
- Added Statistical Continuity Evaluation v0.2 using exact dependency-free one-dimensional empirical Wasserstein-1 distance.
- Added source/target trial count, mean, sample standard deviation, distribution distance, and per-metric similarity reporting.
- Added per-metric `min_trials` with a default of 5 and explicit required-metric failure on missing or insufficient trial data.
- Added `compare_trial_distributions()` and `rcl compare-trials` with text, JSON, and report-file output.
- Added Robot A / Robot B repeated-trial fixtures and documentation.
- Added regression coverage proving equal means can still receive degraded continuity when empirical distributions differ.
- Added Experiment Context / Measurement Protocol v0.1 with protocol IDs, versions, comparison fields, and session context.
- Added a strict context gate that blocks statistical scoring when protocol or required experiment conditions differ.
- Added machine-readable `context_comparison` results and `context_mismatch` report status with `score: null`.
- Added non-blocking software, adapter, and sensor metadata differences so different robot implementations can still be compared under the same external scenario.
- Added reference person-following protocol metadata and context-aware Robot A / Robot B trial fixtures.
- Added tests for environment mismatch, missing required context, protocol-version mismatch, and informational implementation differences.
- Expanded the roadmap toward repeated-session uncertainty and real-robot validation.

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
