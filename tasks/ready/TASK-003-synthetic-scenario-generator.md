# TASK-003: Synthetic scenario generator + answer keys

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection/graph (C)
- **depends_on:** TASK-001
- **human_authorization:** no

## Objective

Build a generator producing at least three fraud scenarios (duplicate-like
case, cycle case, fan-in/fan-out case — per the operating pack's "first 3
hours" plan) as canonical fixtures, each with a hidden-from-the-agent
answer key. Use AMLSim-style patterns (`research/fraud/README.md`) plus at
least one hand-built shell-company/kickback ring grounded in the
SAT/CFDI domain (`docs/regulatory/`).

## Allowed paths

```
data/synthetic/**
data/answer_keys/**
tests/scenarios/**
domain/entities/**   (read-only use, no changes)
```

## Forbidden paths

```
domain/schemas/**
frontend/**
agent/**
```

## Input

`domain/schemas/`, `research/fraud/README.md` (AMLSim patterns).

## Output

`data/synthetic/scenario-*.json` fixtures + matching
`data/answer_keys/scenario-*.json` (expected leads, path, evidence,
amount, conclusion, discarded leads — see `docs/testing.md`).

## Acceptance criteria

- [ ] At least 3 scenarios: duplicate-like, cycle, fan-in/fan-out.
- [ ] At least 1 scenario is a hand-built EFOS-style shell/kickback ring.
- [ ] Answer keys are stored separately from the scenario data and are
      never read by `agent/` code.

## Tests required

`tests/scenarios/` fixtures load and validate against `domain/schemas/`.

## Documentation requirements

`data/synthetic/README.md` and `data/answer_keys/README.md` updated with
what each scenario represents.
