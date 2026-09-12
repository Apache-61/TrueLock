# TASK-020: Investigation state machine

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-008, TASK-009
- **human_authorization:** no

## Objective

Implement the investigation state described in `docs/investigation/protocol.md`: the object that tracks one investigation from a lead through the steps taken, the tools called, the evidence gathered and the conclusion reached.

The agent loop (TASK-021) drives this; the API (TASK-037) serves it; the timeline UI (TASK-041) renders it. It is the shared spine of the investigation half of the product, so define it before the loop that mutates it.

## Allowed paths

```
agent/runtime/state.py
agent/runtime/__init__.py
tests/**
```

## Forbidden paths

```
database/**
frontend/**
detection/**
domain/schemas/**
```

## Acceptance criteria

- [ ] An investigation records every step in order, with the tool called, its arguments, and the result's provenance.
- [ ] State transitions are explicit and illegal transitions are refused.
- [ ] The state serializes to and from the TASK-008 `InvestigationStep` entities without loss.
- [ ] State can be rehydrated mid-investigation, so a crash does not lose the work already done.

## Tests required

`tests/unit/` for transitions, ordering, and serialization round-trip.

## Documentation requirements

Update `agent/runtime/README.md` with the state diagram.
