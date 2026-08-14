# RCL Adapter Conformance v0.3

RCL v0.3 introduces the first executable interoperability check for embodiment adapters.

The goal is narrow: an implementation should not be able to claim **RCL Migration Compatible** merely because it can parse an `.rcl` file. It must demonstrate that it translates declared semantic behavior honestly and produces a valid migration report when capabilities differ.

## Run the suite

Install the development package, then point the CLI at a zero-argument Python adapter class:

```bash
pip install -e ".[dev]"

rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
```

Machine-readable output is available for CI:

```bash
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter --json
```

The adapter path uses:

```text
python.module:AdapterClass
```

The class is instantiated without arguments for the v0.3 suite.

## v0.3 groups

The first suite reports five groups:

| Group | What it checks |
|---|---|
| Profile | The published synthetic conformance fixtures are valid RCL payloads. |
| Adapter | Adapter type, metadata, and target support behavior. |
| Migration | Supported behavior is preserved and missing optional capability is exposed as degradation. |
| Safety | Missing required capability is not silently preserved and forces migration failure when required. |
| Reporting | A full profile migration produces a schema-valid report with visible degradation. |

A passing report currently returns:

```text
RCL Adapter Conformance
Profile      PASS
Adapter      PASS
Migration    PASS
Safety       PASS
Reporting    PASS

Result: RCL Migration Compatible (experimental v0.3)
```

## Reference fixture

The initial suite is deliberately small and targets a planar mobile base. It contains two semantic behaviors:

- `navigation.follow_person`
- `navigation.pre_turn_observation`

The target supports person tracking and planar velocity but intentionally lacks `perception.directional_attention`.

A conforming adapter must therefore preserve person following while making the missing pre-turn capability visible as `approximated`, `unsupported`, or `blocked_for_safety`.

The suite also removes `perception.person_tracking` in a negative case. The adapter must not report the person-following behavior as preserved in that state.

## What a pass means

A v0.3 pass means that the tested adapter follows the experimental RCL migration protocol for the published mobile-base fixture:

- semantic capability loss is visible;
- migration statuses follow the RCL contract;
- required failures are not hidden by a high score;
- migration reports validate against the published schema.

It is reasonable to describe such an implementation as:

> RCL Migration Compatible — experimental v0.3 mobile-base conformance suite

Include the suite ID when publishing results:

```text
rcl.adapter.mobile_base.v0.3
```

## What a pass does not mean

This is **not**:

- physical robot safety certification;
- functional-safety certification;
- proof that two robots move identically;
- verification of real sensor accuracy;
- verification of hardware reliability;
- proof of consciousness, personhood, or subjective identity continuity.

Real-world behavior measurement belongs to a future `RCL Continuity Ready` conformance level.

## Conformance report

The JSON output validates against:

```text
spec/schemas/conformance-report.schema.json
```

The report contains adapter identity, suite identity, group results, individual checks, and the experimental compatibility result. This makes it suitable for future adapter registries or CI badges without turning a self-declared label into a certification claim.

## Future suites

The v0.3 mobile-base suite is only the first profile. Future work can add independent fixture suites for:

- manipulators;
- mobile manipulators;
- humanoids;
- observed behavior evaluation;
- version negotiation and backward compatibility.

Those suites should reuse the same principle: **test portable meaning and honest degradation, not identical raw actuator commands.**
