# TASK-006: Frontend shell against mocked API

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend (A)
- **depends_on:** none (builds against the mocked contract, not the real backend)
- **human_authorization:** no

## Objective

Stand up the Next.js/TypeScript shell for the screens in
`docs/demo/runbook.md`: dashboard, investigation view, graph, money trail,
evidence, case file, Q&A — wired to a mock implementation of
`docs/contracts/api.md` (static fixtures, no real backend needed yet).

## Allowed paths

```
frontend/**
docs/contracts/api.md   (may propose changes, not finalize alone)
```

## Forbidden paths

```
domain/**
detection/**
database/**
agent/**
```

## Input

`docs/contracts/api.md`, `docs/demo/runbook.md`, `research/graph/README.md`
(Cytoscape.js).

## Output

A running frontend showing all required screens against mock data,
including the observability timeline shape from `docs/contracts/api.md`.

## Acceptance criteria

- [ ] Every endpoint in `docs/contracts/api.md` has a mock fixture and a
      page/component consuming it.
- [ ] Graph screen renders a small mock graph via Cytoscape.js.
- [ ] Swapping the mock for the real API later requires no component
      changes, only a data-source swap.

## Tests required

Component tests for each screen against the mock fixtures.

## Documentation requirements

`frontend/README.md` updated with how to run it and where the mock lives.
