# Repeated-Session Confidence / Uncertainty v0.1

RCL's single-session Statistical Continuity Evaluation answers whether Robot B behaves like Robot A over repeated trials **inside one comparable experiment session**.

Repeated-Session Confidence adds a second time scale:

```text
Day 1: Robot A ↔ Robot B repeated-trial score
Day 2: Robot A ↔ Robot B repeated-trial score
Day 3: Robot A ↔ Robot B repeated-trial score
                    ↓
          equal-weight session series
                    ↓
     mean + between-session variation
                    ↓
          95% Student-t interval
```

The goal is to report how stable continuity appears across sessions without pretending that a small number of sessions provides high certainty.

## Why sessions are equally weighted

A session is the unit of longitudinal evidence. If Day 1 contains 100 trials and Day 2 contains 10 trials, giving Day 1 ten times more weight would mostly measure the amount of data collected that day rather than day-to-day continuity.

RCL therefore calculates one Statistical Continuity Score per session and gives every session one equal vote in the repeated-session summary.

## Minimum session count

The experimental default is:

```text
min_sessions = 3
confidence_level = 0.95
```

With fewer than three scorable sessions, RCL can still report the available mean and sample standard deviation, but it does not publish the repeated-session confidence interval and `evaluation_success` remains false.

## 95% confidence interval

For session scores `x1 ... xn`:

```text
mean = Σxi / n
s    = sample standard deviation
SE   = s / sqrt(n)
CI   = mean ± t(0.975, n-1) × SE
```

RCL uses Student's t for small samples rather than immediately using the large-sample normal value `1.96`.

Examples of two-sided 95% critical values:

```text
n=3  -> df=2 -> t=4.303
n=4  -> df=3 -> t=3.182
n=5  -> df=4 -> t=2.776
```

The reported score interval is clipped to the valid score range `0..100`. Per-metric similarity intervals are clipped to `0..1`.

## Series comparability

Before session scores are aggregated, the series must describe the same experiment family.

RCL v0.1 requires the same:

- source robot ID and embodiment ID;
- target robot ID and embodiment ID;
- experiment protocol ID and version;
- protocol comparison-field list;
- values of those comparison fields.

A changed room, task, subject, or starting condition that is part of the protocol comparison key therefore creates `series_mismatch` instead of being silently mixed into between-session variability.

This is deliberately strict. Multi-context or stratified longitudinal evaluation can be added later as a separate protocol.

## Session failures are not averaged away

A context mismatch produces no session score. A required-metric failure may still produce a numerical session score, but the session remains failed.

Repeated-session evaluation keeps these failures explicit:

```text
failed_session_count
failed_session_ids
context_mismatch_session_ids
```

If any session fails, the repeated-session `evaluation_success` is false even if the numerical average remains high.

## Per-metric uncertainty

RCL also groups session-level metric similarities by `(behavior_id, metric_id, unit)` and reports:

- number of sessions contributing a numeric similarity;
- mean similarity;
- between-session sample standard deviation;
- 95% Student-t interval when enough sessions exist.

This helps identify cases where the overall score looks stable but one specific behavior varies strongly between days.

## Manifest format

The CLI uses a relocatable manifest whose trial paths are resolved relative to the manifest file:

```json
{
  "session_manifest_version": "0.1",
  "confidence_level": 0.95,
  "min_sessions": 3,
  "sessions": [
    {
      "session_id": "day-1",
      "source_trials": "../trials/demo-rover-a.trials.json",
      "target_trials": "../trials/demo-rover-b.trials.json"
    },
    {
      "session_id": "day-2",
      "source_trials": "day2-rover-a.trials.json",
      "target_trials": "day2-rover-b.trials.json"
    }
  ]
}
```

Run:

```bash
rcl compare-sessions \
  examples/mobile-base \
  examples/sessions/demo-rover-a-b.sessions.json
```

JSON output:

```bash
rcl compare-sessions \
  examples/mobile-base \
  examples/sessions/demo-rover-a-b.sessions.json \
  --json
```

## Status values

- `estimated` — at least the configured minimum number of scorable sessions, no failed sessions, and one comparable series.
- `insufficient_sessions` — some sessions are scorable but not enough for the configured uncertainty estimate.
- `session_failures` — at least one session failed its context or required behavior evaluation.
- `no_scorable_sessions` — no session produced a statistical score.
- `series_mismatch` — the sessions do not describe one comparable robot/protocol/context series.

## What v0.1 does not claim

Repeated-Session Confidence does **not** define a universal threshold for whether two robots are the same robot, prove subjective identity, certify physical safety, or establish a formal longitudinal equivalence test.

It is an uncertainty report over explicit session-level continuity measurements. Acceptance thresholds should be introduced only with application-specific evidence and risk requirements.
