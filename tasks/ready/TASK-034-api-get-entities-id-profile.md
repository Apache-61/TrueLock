# TASK-034: API: GET /entities/{id} profile

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032
- **human_authorization:** no

## Objective

Serve an entity profile: identity fields, EFOS status where known, counterparty summary, invoice and payment totals, and the leads that reference it. The screen a user reaches by clicking any entity anywhere in the UI.

## Allowed paths

```
backend/api/routes/entities.py
```

## Forbidden paths

```
backend/api/main.py
frontend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Totals are computed in the query, not by loading every record into memory.
- [ ] An unknown entity id returns the documented 404 shape.
- [ ] Response shape matches `docs/contracts/api.md`.

## Tests required

`tests/integration/` for a known entity, an entity with no activity, and not-found.

## Documentation requirements

Update `backend/api/README.md`.
