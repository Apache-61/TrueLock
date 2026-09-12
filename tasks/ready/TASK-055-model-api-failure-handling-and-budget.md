# TASK-055: Model API failure handling and budget guard

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-022
- **human_authorization:** no

## Objective

Handle the ways a model provider fails -- rate limits, timeouts, malformed responses, quota exhaustion -- with bounded retry, provider rotation through the existing `orchestrator/routing/` pool, and a hard budget stop.

The budget is ~USD 300 across four projects. A runaway loop can spend it in an afternoon, so the guard must be a hard stop, not a warning.

## Allowed paths

```
agent/runtime/resilience.py
```

## Forbidden paths

```
frontend/**
detection/**
backend/**
agent/runtime/loop.py
```

## Acceptance criteria

- [ ] Each failure mode has a distinct, tested behaviour -- no bare catch-all.
- [ ] Retries are bounded with backoff and never unbounded.
- [ ] Exhausting one provider's quota rotates to the next and logs a `ROUTING_EVENT`.
- [ ] Reaching the budget ceiling stops further calls rather than warning and continuing.
- [ ] Every failure and rotation lands in the usage ledger.

## Tests required

`tests/unit/` per failure mode against a stubbed transport, including the budget-ceiling stop.

## Documentation requirements

Update `agent/runtime/README.md` and `orchestrator/policies/provider-pool.yaml` notes.
