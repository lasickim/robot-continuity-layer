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

Result: RCL Migration Compatible (experimental suite 0.3)
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

## Intent-aware v0.4 suite

RCL v0.4 also provides a separate opt-in suite for adapters that claim to preserve **Behavior Intent / Goal Semantics** and alternative capability paths.

```bash
rcl-conformance intent rcl:CapabilityPathReferenceAdapter
```

This suite checks that an adapter:

- keeps alternative capability paths as alternatives instead of flattening them into one all-required set;
- reports a selected path that the target actually satisfies;
- preserves the same declared goal through a different valid target path;
- fails honestly when no functional path is satisfied;
- does not use a reproducible legacy expression as a substitute for functional Intent satisfaction;
- exposes complete path diagnostics in migration reports;
- preserves legacy flat `required_capabilities` compatibility.

A passing implementation receives the experimental label:

```text
RCL Intent Migration Compatible
```

Suite ID:

```text
rcl.adapter.intent.v0.4
```

See [`INTENT_CONFORMANCE.md`](INTENT_CONFORMANCE.md) for the full contract.

The existing v0.3 mobile-base suite remains unchanged. An adapter may be tested against either or both suites depending on the interoperability claim it makes.

## What a pass does not mean

These suites are **not**:

- physical robot safety certification;
- functional-safety certification;
- proof that two robots move identically;
- verification of real sensor accuracy;
- verification of hardware reliability;
- proof that a declared Intent was actually achieved in the physical world;
- proof of consciousness, personhood, or subjective identity continuity.

Observed goal achievement remains a separate `Observed Intent Success` question. Real-world behavior measurement remains a separate physical/evaluation layer.

## Conformance reports

The v0.3 JSON output validates against:

```text
spec/schemas/conformance-report.schema.json
```

The Intent-aware v0.4 JSON output validates against:

```text
spec/schemas/intent-conformance-report.schema.json
```

Reports contain adapter identity, suite identity, group results, individual checks, and the experimental compatibility result. This makes them suitable for future adapter registries or CI badges without turning a self-declared label into a physical certification claim.

## Future suites

The current suites cover mobile-base migration and Intent/capability-path report honesty. Future work can add independent fixture suites for:

- manipulators;
- mobile manipulators;
- humanoids;
- observed behavior evaluation;
- version negotiation and backward compatibility.

Those suites should reuse the same principle: **test portable meaning and honest degradation, not identical raw actuator commands.**
