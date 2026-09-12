# TASK-001: Canonical domain data ingestion & normalization

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend/data (B)
- **depends_on:** none (domain contracts already frozen in this bootstrap)
- **human_authorization:** no (implements existing contracts, doesn't change them)

## Objective

Implement `domain/entities/` (Pydantic models matching `domain/schemas/`)
and `scripts/ingest/` normalizers that turn raw CFDI/CSV-style records
into canonical `Provider`/`Invoice`/`Payment`/`Transaction`/`Account`
objects.

## Allowed paths

```
domain/entities/**
backend/repositories/**
scripts/ingest/**
```

## Forbidden paths

```
domain/schemas/**   (frozen contract, do not modify)
frontend/**
agent/**
detection/rules/**
```

## Input

`domain/schemas/*.schema.json`, `docs/contracts/domain.md`.

## Output

Python classes + a normalization function per source format, unit-tested.

## Acceptance criteria

- [ ] Every schema in `domain/schemas/` has a corresponding entity class.
- [ ] A malformed record is rejected with a clear error, not
      best-effort-guessed (`SECURITY.md`).
- [ ] Round-trips: entity → dict → entity produces an identical object.

## Tests required

`tests/unit/` for each entity's validation; `tests/contract/` checks the
entity's serialized shape matches its JSON Schema.

## Documentation requirements

Update `domain/entities/README.md` with what's implemented.
