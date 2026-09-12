# TASK-XXX: <short title>

- **type:** feature | bug | research | experiment | integration | documentation | security | decision
- **priority:** P0 | P1 | P2 | P3
- **status:** RESEARCH | PROPOSAL | WAITING_AUTHORIZATION | READY | CLAIMED | IN_PROGRESS | TESTING | READY_FOR_REVIEW | MERGED | VERIFIED | BLOCKED | REJECTED | CANCELLED
- **execution_mode:** auto | human
- **owner (area):** frontend (A) | backend/data (B) | detection/graph (C) | agent/evidence (D) | shared
- **depends_on:** [TASK-YYY, ...] (or none)
- **human_authorization:** yes/no — if yes, who and when

## Objective

One or two sentences: what this task accomplishes and why it's needed now.

## Allowed paths

```
path/one/**
path/two/file.ext
```

## Forbidden paths

```
path/that/belongs/to/another/module/**
```

## Input

What exists already that this task consumes (a contract, a fixture, a
prior task's output).

## Output

What this task produces, concretely (a file, an endpoint, a passing test
suite).

## Acceptance criteria

- [ ] ...
- [ ] ...

## Tests required

What must pass before this can move to `READY_FOR_REVIEW`.

## Documentation requirements

What docs/READMEs must be updated as part of this task (module README,
`docs/contracts/*`, `PROJECT_STATE.md`, `CHANGELOG.md` if product-visible).

## Definition of done

References `CONTRIBUTING.md` §6. Add anything task-specific here.
