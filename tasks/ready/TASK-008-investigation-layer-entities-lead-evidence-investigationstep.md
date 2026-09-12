# TASK-008: Investigation-layer entities: Lead, Evidence, InvestigationStep, Case

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-001
- **human_authorization:** no

## Objective

Implement the entity classes for the investigation half of the domain, matching the frozen schemas: `lead.schema.json`, `evidence.schema.json`, `investigation_step.schema.json`, `case.schema.json`, `detector_signal.schema.json`.

These are the types every later module exchanges: detectors emit `DetectorSignal` and `Lead`, the agent emits `InvestigationStep` and `Evidence`, case generation emits `Case`. Get the shapes right here and the rest of the system has a common vocabulary.

## Allowed paths

```
domain/entities/**
tests/**
```

## Forbidden paths

```
domain/schemas/**
frontend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Every investigation-side schema has a corresponding entity class.
- [ ] Round-trips: entity -> dict -> entity produces an identical object.
- [ ] An `Evidence` object cannot be constructed without provenance -- the type system enforces what `docs/contracts/evidence.md` requires.
- [ ] A `Case` composes `Lead`, `Evidence` and `InvestigationStep` rather than duplicating their fields.

## Tests required

`tests/unit/` per entity; `tests/contract/` asserts each entity's serialized shape matches its JSON Schema.

## Documentation requirements

Update `domain/entities/README.md`.
