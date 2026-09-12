# TASK-010: Seed loader: synthetic scenarios into the database

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** data
- **depends_on:** TASK-002, TASK-003
- **human_authorization:** no

## Objective

A single command that loads a generated scenario from TASK-003 into the database built by TASK-002, so every developer and every demo starts from an identical, named dataset.

This is the join between 'we can generate data' and 'the product has data to work on' -- it is on the critical path to the vertical slice.

## Allowed paths

```
scripts/ingest/load_scenario.py
database/seeds/**
```

## Forbidden paths

```
domain/schemas/**
frontend/**
agent/**
detection/**
```

## Acceptance criteria

- [ ] `load_scenario --scenario <name>` populates an empty database end to end with no manual step.
- [ ] Loading is idempotent: running it twice does not duplicate rows.
- [ ] The loader refuses to run against a database with existing data unless explicitly told to reset, so nobody destroys a working demo by accident.
- [ ] Answer keys are NOT loaded into the database -- they stay test-only.
- [ ] Load time for the demo scenario is reported, and is fast enough to re-run during the demo.

## Tests required

`tests/integration/` loads a scenario into a scratch database and asserts row counts against the fixture.

## Documentation requirements

Document the load command in `database/README.md` and `docs/demo/runbook.md`.
