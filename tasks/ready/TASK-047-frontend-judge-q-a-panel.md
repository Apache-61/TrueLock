# TASK-047: Frontend: judge Q&A panel

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-039
- **human_authorization:** no

## Objective

Ask questions about a case and render the grounded answer with its citations. Used live, in front of judges, on unscripted questions.

## Allowed paths

```
frontend/app/qa/**
frontend/components/qa/**
tests/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] The answer renders with citations linking to evidence.
- [ ] A pending answer shows progress, so a slow model call does not look like a hang.
- [ ] An 'evidence does not show that' answer is rendered as a legitimate answer, not an error.
- [ ] A failed request is recoverable without reloading the page.

## Tests required

Component tests for answered, unanswerable, pending and failed states.

## Documentation requirements

Update `frontend/README.md`.
