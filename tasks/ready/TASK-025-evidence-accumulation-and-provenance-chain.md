# TASK-025: Evidence accumulation and provenance chain

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** evidence
- **depends_on:** TASK-008, TASK-005
- **human_authorization:** no

## Objective

Turn tool results into `Evidence`: collect what the investigation found, deduplicate it, rank it by strength, and keep every item's chain back to the source records.

`docs/contracts/evidence.md` is the contract. The rule that matters: no evidence without provenance. An unsourced claim must be impossible to add, not merely discouraged.

## Allowed paths

```
evidence/**
tests/**
```

## Forbidden paths

```
frontend/**
detection/**
database/**
agent/runtime/**
```

## Acceptance criteria

- [ ] Evidence cannot be created without source record ids.
- [ ] The same finding reached by two tools is deduplicated, keeping both provenance paths.
- [ ] Evidence is ranked by a documented strength measure.
- [ ] The full chain from a conclusion back to source records can be walked programmatically.
- [ ] Contradictory evidence is retained and marked, not silently dropped.

## Tests required

`tests/unit/` for provenance enforcement, deduplication, ranking, and the contradiction case.

## Documentation requirements

Update `evidence/README.md`.
