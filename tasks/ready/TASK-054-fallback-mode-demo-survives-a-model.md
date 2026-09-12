# TASK-054: Fallback mode: demo survives a model outage

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** infra
- **depends_on:** TASK-022, TASK-049
- **human_authorization:** no

## Objective

Let the demo run end to end with no live model call, by replaying recorded investigation responses for the demo scenario.

The deterministic half of the product -- detection, leads, graph, money trail -- does not need a model at all. Fallback mode must keep that fully live and replay only the agent's narration, so a provider outage costs polish rather than the demo.

## Allowed paths

```
agent/runtime/fallback.py
data/recorded/**
```

## Forbidden paths

```
frontend/**
detection/**
backend/**
agent/runtime/loop.py
```

## Acceptance criteria

- [ ] The full demo path runs with the model provider unreachable.
- [ ] Fallback mode is visibly indicated in the UI -- it is never presented as a live investigation.
- [ ] Switching to fallback is one documented flag, usable under pressure.
- [ ] Deterministic detection, graph and money trail remain fully live in fallback mode.

## Tests required

`tests/e2e/` runs the demo path with the provider stubbed unreachable.

## Documentation requirements

Document the flag and what it changes in `docs/demo/runbook.md`.
