# TASK-001: Canonical domain data ingestion & normalization

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** data
- **depends_on:** none
- **human_authorization:** no

## Objective

Implement `domain/entities/` (Pydantic models matching `domain/schemas/`) and `scripts/ingest/` normalizers that turn raw CFDI/CSV-style records into canonical `Provider`/`Invoice`/`Payment`/`Transaction`/`Account` objects, plus the repository interfaces in `backend/repositories/` that every later module reads through.

Input: `domain/schemas/*.schema.json`, `docs/contracts/domain.md`. The schemas are a frozen contract -- implement them, do not edit them.

## Allowed paths

```
domain/entities/**
scripts/ingest/**
backend/repositories/**
```

## Forbidden paths

```
domain/schemas/**
frontend/**
agent/**
detection/**
```

## Acceptance criteria

- [ ] Every schema in `domain/schemas/` for a canonical entity has a corresponding entity class.
- [ ] A malformed record is rejected with a clear error, not best-effort-guessed (`SECURITY.md`).
- [ ] Round-trips: entity -> dict -> entity produces an identical object.
- [ ] `backend/repositories/` exposes a read interface per entity that later modules can depend on without importing the database driver.

## Tests required

`tests/unit/` for each entity's validation; `tests/contract/` checks the entity's serialized shape matches its JSON Schema.

## Documentation requirements

Update `domain/entities/README.md` with what is implemented.
