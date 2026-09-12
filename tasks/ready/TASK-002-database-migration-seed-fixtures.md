# TASK-002: Database migration & seed fixtures

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** database
- **depends_on:** TASK-001
- **human_authorization:** no

## Objective

Stand up PostgreSQL from `database/migrations/0001_init.sql`, add any missing migration needed once TASK-001's entities are final, and load `database/seeds/` with fixture data.

A structural change to the draft schema touches a shared contract and needs human sign-off first (`CONTRIBUTING.md` 5).

## Allowed paths

```
database/**
```

## Forbidden paths

```
domain/schemas/**
frontend/**
agent/**
```

## Acceptance criteria

- [ ] A clean database can be built from migrations alone, in order, with no manual step.
- [ ] Migrations are idempotent to re-run and each has a documented forward path.
- [ ] `database/seeds/` loads without error against the migrated schema.
- [ ] Every canonical entity from TASK-001 has a table whose columns match the entity's fields.

## Tests required

`tests/integration/` builds a scratch database from migrations and asserts the seed load succeeds and row counts match the fixtures.

## Documentation requirements

Update `database/README.md` and `database/migrations/README.md`.
