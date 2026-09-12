# TASK-045: Frontend: evidence panel with provenance

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-037
- **human_authorization:** no

## Objective

Render the evidence an investigation gathered, each item showing its strength and linking back to the source records -- the panel that lets a judge check any claim rather than take it on trust.

## Allowed paths

```
frontend/app/evidence/**
frontend/components/evidence/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Every evidence item links to the records that support it.
- [ ] Items are ordered by strength.
- [ ] Contradictory evidence is shown as such, not hidden.
- [ ] An investigation with no evidence renders an explicit empty state.

## Tests required

Component tests for ranked evidence, the contradiction case, and the empty state.

## Documentation requirements

Update `frontend/README.md`.
