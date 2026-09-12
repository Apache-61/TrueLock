# TASK-006: Frontend shell against mocked API

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** none
- **human_authorization:** no

## Objective

Stand up the Next.js/TypeScript shell for the screens in `docs/demo/runbook.md` -- dashboard, investigation view, graph, money trail, evidence, case file, Q&A -- wired to a mock implementation of `docs/contracts/api.md` (static fixtures, no real backend needed).

This task owns the shell: routing, layout, the API client seam, and the mock. Each screen's real content is a separate task that fills in its own route directory.

## Allowed paths

```
frontend/**
```

## Forbidden paths

```
domain/**
detection/**
database/**
agent/**
```

## Acceptance criteria

- [ ] `npm run build` and `npm run lint` succeed from a clean checkout.
- [ ] Every screen in the demo runbook has a route that renders from mock data.
- [ ] The API client is a single seam: swapping mock for real is a configuration change, not a rewrite of the screens.
- [ ] Mock fixtures match the shapes in `docs/contracts/api.md`.

## Tests required

Component/route smoke tests that each screen renders from the mock without error.

## Documentation requirements

Update `frontend/README.md` with how to run the shell and where the mock lives.
