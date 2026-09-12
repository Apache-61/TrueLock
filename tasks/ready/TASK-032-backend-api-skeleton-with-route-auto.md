# TASK-032: Backend API skeleton with route auto-discovery

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-009
- **human_authorization:** no

## Objective

Stand up the FastAPI application implementing `docs/contracts/api.md`: app factory, dependency wiring to the TASK-009 repositories, the shared error contract, CORS for the frontend, and health/readiness endpoints.

Critically, routers must be auto-discovered from `backend/api/routes/`. Each endpoint task (TASK-033..039) then adds exactly one file and touches nothing shared -- which is what lets four machines build endpoints in parallel without conflicting on a central registration file.

## Allowed paths

```
backend/api/main.py
backend/api/app.py
backend/api/deps.py
backend/api/errors.py
backend/api/routes/__init__.py
tests/**
```

## Forbidden paths

```
frontend/**
detection/**
agent/**
domain/schemas/**
```

## Acceptance criteria

- [ ] Dropping a new module into `backend/api/routes/` registers its routes with no edit to any shared file.
- [ ] Errors follow one documented shape across every endpoint, including validation failures.
- [ ] Health and readiness are distinct: readiness fails when the database is unreachable.
- [ ] The app starts with no database present and reports unready, rather than crashing on import.
- [ ] OpenAPI output matches `docs/contracts/api.md`.

## Tests required

`tests/integration/` for app startup, the error contract, health/readiness, and auto-discovery of a test router.

## Documentation requirements

Update `backend/api/README.md` with how to add an endpoint.
