# TASK-021: Bounded agent loop with stopping conditions

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-005, TASK-020
- **human_authorization:** no

## Objective

Implement the bounded investigation loop from `docs/investigation/protocol.md`: given a lead, decide which tool to call next, call it, record the step, and decide whether to continue.

Bounded is the load-bearing word (ADR-0002). The loop must stop on every one of: a step budget, a wall-clock budget, a token/cost budget, a confidence threshold reached, no new information from the last N steps, or a tool error it cannot route around. An agent that can loop forever on a paid API is the single most expensive bug available to us.

## Allowed paths

```
agent/runtime/loop.py
agent/runtime/stopping.py
agent/policies/**
agent/prompts/investigator.md
tests/**
```

## Forbidden paths

```
database/**
frontend/**
detection/**
agent/runtime/state.py
```

## Acceptance criteria

- [ ] Every stopping condition listed in the objective is implemented and independently tested.
- [ ] The loop cannot exceed its step budget under any input, including a model that keeps requesting tools.
- [ ] Every iteration appends a step to the TASK-020 state before the next call, so an interrupted run still shows what happened.
- [ ] A tool error is recorded and the loop decides explicitly whether to continue -- it never silently retries forever.
- [ ] The loop is testable without calling a real model (inject the model client).

## Tests required

`tests/unit/` with a scripted fake model driving each stopping condition, including the adversarial 'model always asks for another tool' case.

## Documentation requirements

Document the budgets and their defaults in `agent/runtime/README.md`.
