# TASK-036: API: GET /cases/{id}

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032, TASK-008
- **human_authorization:** no

## Objective

Serve the generated case file: narrative, findings, evidence with provenance, money trail, and confidence -- the artefact the demo ends on.

## Allowed paths

```
backend/api/routes/cases.py
tests/**
```

## Forbidden paths

```
backend/api/main.py
frontend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Evidence in the response carries its source record ids, so the UI can link every claim.
- [ ] A case for an investigation that is still running returns a documented 'not ready' response rather than a partial case.
- [ ] An unknown case id returns the documented 404 shape.

## Tests required

`tests/integration/` for a complete case, an in-progress investigation, and not-found.

## Documentation requirements

Update `backend/api/README.md`.
