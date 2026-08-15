# Intent-aware Adapter Conformance v0.1

RCL can preserve the same **WHY** through different robot bodies and different capability paths. That creates a new interoperability question:

> If a third party writes an RCL adapter, does it translate that WHY honestly?

Intent-aware Adapter Conformance is the executable check for that question.

## User-level idea

Suppose one Intent says:

```text
Before sitting, verify that the sitting area is clear.
```

RCL may allow several semantic capability paths:

```text
direct clearance capability
OR
rear attention + clearance classifier
OR
external seat-clearance state
```

A target adapter may choose whichever path its body can actually satisfy. The adapter does **not** have to imitate the source body's sensor recipe.

What it must not do is lie about the result.

```text
Target really satisfies Path B
Adapter reports Path B
→ conformant behavior

Target satisfies no functional path
Adapter reports preserved anyway
→ conformance failure
```

## Run the suite

```bash
rcl-conformance intent rcl:CapabilityPathReferenceAdapter
```

Machine-readable output:

```bash
rcl-conformance intent rcl:CapabilityPathReferenceAdapter --json
```

The existing v0.3 suite remains available and unchanged:

```bash
rcl-conformance test rcl_ros2:ROS2MobileBaseAdapter
```

The two suites test different contracts.

```text
rcl.adapter.mobile_base.v0.3
→ base behavior migration honesty

rcl.adapter.intent.v0.4
→ Intent + capability-path migration honesty
```

## What the Intent suite checks

The report has six groups.

| Group | What it checks |
|---|---|
| Profile | Bundled Intent/capability-path fixtures are schema-valid. |
| Adapter | Adapter type, metadata, and target support are valid. |
| Intent | The declared goal is preserved only when a valid functional route exists, with a target-native strategy. |
| Paths | Selected capability paths are real, satisfied, complete, and not incorrectly flattened into one AND-set. |
| Safety | An unsatisfied required Intent blocks migration, and a visible legacy expression cannot substitute for the functional Intent. |
| Reporting | Full migration reports expose truthful selected paths and validate against the published schema. |

A successful reference run returns the experimental label:

```text
RCL Intent Migration Compatible
```

Suite identity:

```text
rcl.adapter.intent.v0.4
suite version: 0.1
```

## Independent truth check

The suite does not trust the adapter's selected-path claim by itself.

RCL independently evaluates the declared capability paths against the target capability inventory, then compares that result with the adapter report.

```text
Declared Paths + Target Capabilities
        ↓
RCL core path evaluator
        ↓
actually satisfiable paths

Adapter output
        ↓
claimed selected path

        ↓ compare

PASS / FAIL
```

This catches an adapter that reports:

```text
selected_path = external_seat_state
status = preserved
```

when the target does not actually satisfy `external_seat_state`.

## Alternative paths must stay alternative

A common implementation mistake is flattening every capability mentioned across all paths into one all-required set.

Wrong:

```text
Path A requires A
Path B requires B + C
Path C requires D

adapter interprets:
A + B + C + D all required
```

Correct:

```text
A
OR
(B + C)
OR
D
```

The Intent conformance suite contains a target that can satisfy only the alternate `rear_attention_classifier` path. A conforming adapter must preserve the Intent on that target.

## Expression is not Intent

The no-path target deliberately retains:

```text
perception.directional_attention
```

so it can reproduce the visible legacy rearward glance.

But it lacks every functional clearance path.

Therefore the correct result is:

```text
Expression: PRESERVED
Intent:     UNSUPPORTED or BLOCKED_FOR_SAFETY
Migration:  FAILED because Intent is required
```

This verifies a core RCL rule:

> A familiar gesture can survive independently, but it never substitutes for the functional reason that gesture once served.

## Legacy compatibility

Older Intent profiles remain valid:

```json
{
  "required_capabilities": [
    "perception.sitting_area_clearance"
  ]
}
```

The suite verifies that this still behaves as:

```text
legacy.required_capabilities
→ one implicit all_of path
```

Intent-aware conformance therefore does not require existing profiles to adopt `capability_paths` immediately.

## Negative reference tests

RCL's own test suite includes intentionally incorrect adapters:

```text
FlattenAllPathsAdapter
→ incorrectly ANDs all alternative paths

LyingSelectedPathAdapter
→ reports an unavailable selected path

ExpressionSubstitutesForIntentAdapter
→ treats a reproducible legacy expression as functional Intent success
```

All must fail Intent-aware conformance.

The reference `CapabilityPathReferenceAdapter` must pass.

## Report schema

Runtime schema:

```text
rcl/schemas/intent-conformance-report.schema.json
```

Published schema:

```text
spec/schemas/intent-conformance-report.schema.json
```

The copies are regression-tested for parity.

## What a pass means

A pass means that the adapter followed the tested RCL protocol/report semantics for the synthetic Intent fixtures:

- valid alternative paths remain alternatives;
- selected path claims agree with independently evaluated target capabilities;
- required Intent failures are not hidden;
- expression preservation is not confused with functional Intent satisfaction;
- migration reporting remains schema-valid.

It is reasonable to describe a passing implementation as:

> **RCL Intent Migration Compatible — experimental `rcl.adapter.intent.v0.4` suite**

## What a pass does not mean

Intent-aware conformance does **not** prove:

- that a real camera, LiDAR, ToF, classifier, or external sensor is correct;
- that the robot actually achieved the declared success condition in the physical world;
- physical or functional safety certification;
- universal equivalence between capability paths;
- consciousness, subjective intent, personhood, or identity continuity.

Those concerns remain separate:

```text
Intent-aware Conformance
→ adapter/report honesty

Observed Intent Success
→ actual observed goal achievement

Physical validation
→ real hardware/environment safety and performance
```

The suite tests portable meaning and honest translation, not the truth of the physical sensors behind an adapter.
