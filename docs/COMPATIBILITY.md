# RCL Compatibility

RCL compatibility is intended to describe an implementation's ability to preserve, translate, and report robot continuity data without claiming that two robots are physically identical.

## Experimental compatibility levels

These labels are draft concepts for discussion during the v0.x series. They are not a certification program yet.

### RCL Profile Compatible

An implementation can:

- read and write a valid `.rcl` profile for the declared RCL version;
- validate required profile sections against the published schemas;
- preserve unknown extension fields without silently destroying them where the specification permits extensions;
- verify the package integrity manifest.

### RCL Migration Compatible

An implementation satisfies Profile Compatible requirements and can additionally:

- expose a target embodiment capability description;
- translate supported semantic behaviors into a target-specific execution plan;
- explicitly classify each migrated behavior as `preserved`, `approximated`, `unsupported`, or `blocked_for_safety`;
- produce a machine-readable migration report;
- fail migration success when a required behavior cannot be safely preserved.

### RCL Continuity Ready

A future conformance level intended for real robots. In addition to Migration Compatible requirements, an implementation will be expected to:

- capture or import observed behavior from a live robot;
- restore continuity data to another supported embodiment;
- run a reproducible before/after evaluation;
- report measured continuity separately from declared configuration similarity;
- pass an RCL conformance test kit.

## What compatibility does not mean

RCL compatibility does **not** mean:

- identical motion trajectories;
- identical hardware capability;
- identical safety limits;
- proof of consciousness, personhood, or subjective identity;
- permission to reproduce unsafe legacy behavior.

Safety constraints of the target embodiment always outrank continuity preferences.

## Adapter responsibility

An adapter is responsible for the boundary between semantic continuity and hardware execution:

```text
RCL semantic behavior
        ↓
Embodiment Adapter
        ↓
Target-specific command / policy / controller
```

The adapter should preserve meaning where possible and report degradation where exact preservation is impossible.

## Toward `RCL Compatible`

The long-term goal is for `RCL Compatible` to become a useful interoperability claim backed by an open conformance suite rather than a marketing-only label. Until that suite exists, projects should describe exactly which experimental compatibility level and RCL version they implement.
