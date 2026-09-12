# TASK-024: Agent decision logging

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-020
- **human_authorization:** no

## Objective

Record why the agent did what it did: for each step, the candidate actions considered, the one chosen, the stated reason, and the confidence.

This is what makes the investigation auditable rather than magic, and it is what the live-agent-events UI (TASK-042) and the judge Q&A (TASK-027) both read. A forensic tool whose own reasoning is unauditable defeats its purpose.

## Allowed paths

```
agent/runtime/decision_log.py
tests/**
```

## Forbidden paths

```
frontend/**
detection/**
database/**
agent/runtime/loop.py
```

## Acceptance criteria

- [ ] Every decision entry names the step, the action taken, the reason and the confidence.
- [ ] The log is append-only -- an entry is never rewritten after the fact.
- [ ] Entries are serializable for the event stream and the case file.
- [ ] Logging a decision cannot fail the investigation: a logging error is recorded, not raised into the loop.

## Tests required

`tests/unit/` for append-only behaviour, serialization, and failure isolation.

## Documentation requirements

Update `agent/runtime/README.md`.
