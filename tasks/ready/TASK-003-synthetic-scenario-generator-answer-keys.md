# TASK-003: Synthetic scenario generator + answer keys

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** data
- **depends_on:** TASK-001
- **human_authorization:** no

## Objective

Build a generator producing at least three fraud scenarios (duplicate-like case, cycle case, fan-in/fan-out case) as canonical fixtures, each with an answer key that is hidden from the agent. Use AMLSim-style patterns (`research/fraud/README.md`) plus at least one hand-built shell-company/kickback ring grounded in the SAT/CFDI domain (`docs/regulatory/`).

Reads `domain/entities/` -- does not modify it.

## Allowed paths

```
data/synthetic/**
data/answer_keys/**
data/fixtures/**
```

## Forbidden paths

```
domain/schemas/**
detection/**
agent/**
frontend/**
```

## Acceptance criteria

- [ ] At least three distinct scenarios generate deterministically from a seed, so a run is reproducible.
- [ ] Each scenario ships an answer key naming the entities and the specific records that constitute the fraud.
- [ ] Answer keys live under `data/answer_keys/` and are never read by detection or agent code -- only by tests.
- [ ] Generated records validate against the canonical entities from TASK-001.
- [ ] The generator emits clean (non-fraudulent) background volume too, so a detector that flags everything fails visibly.

## Tests required

`tests/scenarios/` asserts each generated scenario validates and that the answer key references records that actually exist in the fixture.

## Documentation requirements

Document each scenario and its fraud pattern in `data/synthetic/README.md`.
