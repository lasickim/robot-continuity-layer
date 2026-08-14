# Robot Continuity Layer (RCL)

**Status:** Experimental draft v0.2

RCL is an open specification and reference implementation for preserving a robot's experience, preferences, semantic behavior, and skill history independently from its current hardware body.

> **Hardware can be replaced. Experience shouldn't be.**

## v0.2 milestone

RCL v0.2 can now perform a dry-run semantic migration:

```text
Robot A profile
     ↓
.rcl
     ↓
Embodiment Adapter
     ↓
Robot B migration plan
     ↓
Migration Report + Continuity Score
```

The reference demo deliberately uses two different mobile-base embodiments. The target lacks one source capability, so one legacy behavior is reported as an approximation rather than silently treated as preserved.

## Core principles

1. **Semantic before kinematic** — continuity describes observable intent and style, not canonical raw joint/motor values.
2. **Body-independent where possible** — hardware-specific execution belongs in embodiment adapters.
3. **User-owned and portable** — an RCL profile should export without a vendor cloud.
4. **Graceful degradation** — adapters report preserved, approximated, unsupported, or safety-blocked behavior.
5. **Observable continuity** — migration success is measured and inspectable.
6. **Safety outranks continuity** — a legacy quirk never overrides target safety constraints.
7. **Scores do not define identity** — the Continuity Score measures behavior preservation only.

## Repository layout

```text
robot-continuity-layer/
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── spec/
│   ├── rcl-spec-v0.1.md
│   ├── rcl-spec-v0.2.md
│   └── schemas/
│       └── *.schema.json
├── examples/
│   ├── mobile-base/
│   ├── targets/
│   └── migration/
├── rcl/
│   ├── adapter.py
│   ├── example_adapter.py
│   ├── migration.py
│   ├── profile.py
│   ├── score.py
│   ├── cli.py
│   └── schemas/
│       └── *.schema.json
└── tests/
```

## `.rcl` package format

An `.rcl` file is a ZIP container:

```text
robot-a.rcl
├── manifest.json
├── identity.json
├── preferences.json
├── behavior.json
├── skills.json
└── embodiment.json
```

The manifest contains SHA-256 hashes for every payload file.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

rcl validate examples/mobile-base
rcl pack examples/mobile-base /tmp/robot-a.rcl
rcl inspect /tmp/robot-a.rcl

rcl migrate \
  /tmp/robot-a.rcl \
  examples/targets/demo-rover-b.embodiment.json \
  --output /tmp/migration-report.json

rcl report /tmp/migration-report.json
pytest -q
```

Expected reference result:

```text
Continuity Score: 88.33%
Migration Success: YES
- navigation.follow_person: preserved (similarity=1.00)
- navigation.pre_turn_observation: approximated (similarity=0.65)
```

## Continuity Score v0.2

RCL v0.2 uses a transparent weighted semantic similarity score:

```text
required  = weight 4
preferred = weight 2
optional  = weight 1

score = 100 × Σ(weight × similarity) / Σ(weight)
```

A required behavior that is unsupported or blocked for safety makes `migration_success=false` regardless of the numerical score.

## Important boundary

The Continuity Score is **not** a consciousness score, identity proof, emotional authenticity score, or legal personhood measure. It only measures how well declared semantic behaviors survived a migration.

## License

RCL's public core is released under the **Apache License 2.0**. See [`LICENSE`](LICENSE).
