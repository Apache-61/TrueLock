# TASK-046: Frontend: case file view

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-036
- **human_authorization:** no

## Objective

Render the generated case: narrative with inline citations, findings, confidence and its reasoning, and the evidence behind each claim. The screen the demo closes on.

## Allowed paths

```
frontend/app/case/**
frontend/components/case/**
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

- [ ] Every citation in the narrative is a working link to its evidence.
- [ ] Confidence is shown with the reasoning behind it, not as a bare number.
- [ ] A case that is not ready renders a clear in-progress state.
- [ ] The case is readable on a projector: type size and contrast are checked at presentation resolution.

## Tests required

Component tests for a complete case, an in-progress one, and citation links.

## Documentation requirements

Update `frontend/README.md`.
