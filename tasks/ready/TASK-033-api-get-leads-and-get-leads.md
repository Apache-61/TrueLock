# TASK-033: API: GET /leads and GET /leads/{id}

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032, TASK-019
- **human_authorization:** no

## Objective

Serve the scored leads produced by the TASK-019 pipeline: a filterable, paginated list ordered by score, and a single lead with its detector signals and their source records. This is what the dashboard opens with.

## Allowed paths

```
backend/api/routes/leads.py
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

- [ ] The list is paginated and ordered by score descending by default.
- [ ] Filtering by status and by detector type works and is documented.
- [ ] A single lead includes the signals and the source record ids behind it.
- [ ] An unknown lead id returns the documented 404 error shape.
- [ ] Response shapes match `docs/contracts/api.md`.

## Tests required

`tests/integration/` against a seeded database: list, pagination, filters, single, and not-found.

## Documentation requirements

Update `backend/api/README.md`.
