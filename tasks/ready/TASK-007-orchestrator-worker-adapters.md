# TASK-007: Orchestrator worker adapters

- **type:** integration
- **priority:** P1
- **status:** READY
- **execution_mode:** human
- **owner (area):** shared
- **depends_on:** none (`scripts/orchestration/task_cli.py` from the
  bootstrap already implements claim/verify)
- **human_authorization:** yes — adds real API-calling workers, which is
  new infrastructure per `CONTRIBUTING.md` §5.

## Objective

Add `orchestrator/workers/claude.py` and `orchestrator/workers/gemini.py`
adapters that, given a claimed task, invoke the respective CLI/API to
implement it, capture the result, run tests, and write the
`task-result.json` handoff (`orchestrator/README.md`). This automates the
"AI task execution protocol" beyond the manual claim/verify step already
built.

## Allowed paths

```
orchestrator/workers/**
orchestrator/routing/**
orchestrator/policies/**
scripts/orchestration/**
```

## Forbidden paths

```
domain/**
detection/**
agent/**
frontend/**
```

## Input

`orchestrator/README.md`, `scripts/orchestration/task_cli.py`,
`orchestrator/policies/provider-pool.yaml`.

## Output

A worker adapter that can be pointed at a `READY` task and produce a PR +
handoff without a human manually running each step — while still stopping
at every human-authorization boundary in `CONTRIBUTING.md` §5.

## Acceptance criteria

- [ ] Never auto-merges (`CONTRIBUTING.md` §5, operating pack §49 —
      "Auto-merge significant change: NO").
- [ ] Logs every provider-routing decision
      (`ROUTING_EVENT from/to/reason`, see
      `research/infrastructure/README.md`'s fallback matrix and
      `orchestrator/policies/provider-pool.yaml`).
- [ ] Records token usage per call against the usage ledger schema.

## Tests required

A dry-run mode that exercises claim → mock-implement → handoff without
calling a real paid API.

## Documentation requirements

`orchestrator/README.md` updated with real usage instructions.
