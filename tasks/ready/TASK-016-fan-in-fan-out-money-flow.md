# TASK-016: Fan-in / fan-out money-flow detector

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** graph
- **depends_on:** TASK-004, TASK-012
- **human_authorization:** no

## Objective

On the TASK-012 graph, detect fan-in (many sources converging on one account in a short window) and fan-out (one source dispersing to many accounts), the classic layering shapes from `research/fraud/`.

Emit detector signals through the TASK-004 registry so leads are scored the same way as every other rule.

## Allowed paths

```
detection/graph/fan_patterns.py
detection/rules/fan_patterns.py
tests/**
```

## Forbidden paths

```
detection/graph/builder.py
detection/rules/base.py
frontend/**
agent/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] Fan-in and fan-out are separately identifiable signal types.
- [ ] The degree and time-window thresholds are documented and tunable.
- [ ] A payroll or tax account with naturally high degree does not fire -- document the exclusion.
- [ ] Each signal names the centre account and the counterparty record ids.

## Tests required

`tests/unit/` on a hand-built graph; `tests/scenarios/` against the fan-in/fan-out answer key.

## Documentation requirements

Add the patterns to `docs/detection/rules.md` and `detection/graph/README.md`.
