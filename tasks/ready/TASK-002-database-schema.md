# TASK-002: Database migration & seed fixtures

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend/data (B)
- **depends_on:** TASK-001
- **human_authorization:** no, unless the draft schema in
  `database/migrations/0001_init.sql` needs a structural change — that
  would touch a shared contract and needs sign-off first.

## Objective

Stand up PostgreSQL from `database/migrations/0001_init.sql`, add any
missing migration needed once TASK-001's entities are final, and load
`database/seeds/` with fixture data from `data/fixtures/`.

## Allowed paths

```
database/**
scripts/validate/**
```

## Forbidden paths

```
domain/schemas/**
frontend/**
agent/**
```

## Input

`database/migrations/0001_init.sql`, `data/fixtures/`.

## Output

A running local Postgres (or SQLite fallback per `ARCHITECTURE.md` §4)
loadable from a single script.

## Acceptance criteria

- [ ] `database/migrations/0001_init.sql` applies cleanly.
- [ ] Seed data round-trips through the entities from TASK-001.
- [ ] SQLite fallback path documented and tested at least once.

## Tests required

`tests/integration/` — load fixtures, query back, compare.

## Documentation requirements

`database/README.md` updated with actual run instructions.
