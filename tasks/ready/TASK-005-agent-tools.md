# TASK-005: Agent tool implementations

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent/evidence (D), with backend/data (B) for the query layer
- **depends_on:** TASK-002 (database), TASK-004 (leads to investigate)
- **human_authorization:** no

## Objective

Implement every tool in `docs/contracts/agent-tools.md` as read-only
functions over the database/graph, each returning the required
`result/provenance/source_ids/execution_time/errors` shape. Wire the
bounded investigation loop from `docs/investigation/protocol.md`.

## Allowed paths

```
agent/**
evidence/**
```

## Forbidden paths

```
database/**    (consume via backend/repositories, don't reshape it)
frontend/**
```

## Input

`docs/contracts/agent-tools.md`, `docs/investigation/protocol.md`,
`docs/contracts/investigation.md`, `docs/contracts/evidence.md`.

## Output

Working tool functions + a bounded agent loop that produces
`InvestigationStep` and `Evidence` records for a given `Lead`.

## Acceptance criteria

- [ ] Every tool from the contract exists and returns the exact shape.
- [ ] The agent never has write access to the database or this repo
      (`SECURITY.md`).
- [ ] The loop terminates (hop limits + step budget,
      `docs/investigation/protocol.md`).

## Tests required

`tests/contract/` for each tool's response shape; `tests/integration/`
for `lead → investigation → evidence` end to end on a TASK-003 fixture.

## Documentation requirements

`agent/tools/README.md`, `agent/runtime/README.md`, `evidence/README.md`
updated with what's implemented vs. still mocked.
