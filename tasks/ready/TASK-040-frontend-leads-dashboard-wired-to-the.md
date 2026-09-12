# TASK-040: Frontend: leads dashboard wired to the real API

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-033
- **human_authorization:** no

## Objective

Replace the dashboard's mock with the real `/leads` endpoint: the ranked lead list, each lead's score and detector, and the action that starts an investigation. The demo's opening screen.

## Allowed paths

```
frontend/app/dashboard/**
frontend/components/dashboard/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Leads load from the API, ordered by score, with pagination.
- [ ] Loading, empty and error states are all handled visibly -- no blank screen on a failed fetch.
- [ ] Starting an investigation navigates to the investigation view.
- [ ] No mock fixture remains in the dashboard path.

## Tests required

Component tests for the loaded, empty and error states against a stubbed client.

## Documentation requirements

Update `frontend/README.md`.
