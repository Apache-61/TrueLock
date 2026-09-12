# TASK-009: Investigation persistence repositories

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-002, TASK-008
- **human_authorization:** no

## Objective

Persist the investigation-layer entities: migrations for leads, evidence, investigation steps and cases, plus the repository implementations that read and write them.

The agent's investigation state (TASK-020) and the API (TASK-035) both depend on this being the single place investigation data is stored.

## Allowed paths

```
backend/repositories/**
database/migrations/**
tests/**
```

## Forbidden paths

```
domain/schemas/**
frontend/**
agent/**
detection/**
```

## Acceptance criteria

- [ ] Leads, evidence, investigation steps and cases each round-trip through the database unchanged.
- [ ] An investigation's steps come back in the order they were recorded.
- [ ] Migrations follow TASK-002's conventions and re-run cleanly.
- [ ] Repositories expose the queries the agent tools actually need, rather than a generic ORM surface.

## Tests required

`tests/integration/` round-trips each entity against a scratch database.

## Documentation requirements

Update `backend/repositories/README.md`.
