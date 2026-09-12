# TASK-004: Detector framework + first 3 detectors

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection/graph (C)
- **depends_on:** TASK-001, TASK-003 (needs fixtures to test against)
- **human_authorization:** no

## Objective

Implement the detector interface (`docs/contracts/detector.md`), a
registry (`detection/rules/__init__.py`), and the first three detectors:
`DUPLICATE_INVOICE`, `INVOICE_PAYMENT_MISMATCH`, `69B_CORRELATION` (see
`docs/detection/rules.md`). Implement `detection/scoring/` to turn
signals into `Lead`s with a documented threshold.

## Allowed paths

```
detection/**
tests/scenarios/**
domain/entities/**   (read-only use)
```

## Forbidden paths

```
frontend/**
agent/**
domain/schemas/**
```

## Input

`docs/contracts/detector.md`, `docs/detection/rules.md`,
`domain/schemas/detector_signal.schema.json`, `domain/schemas/lead.schema.json`,
`data/synthetic/` fixtures from TASK-003.

## Output

Three working detectors + scoring producing `Lead`s that validate against
`domain/schemas/lead.schema.json`.

## Acceptance criteria

- [ ] Each detector is pure/deterministic (`docs/contracts/detector.md`).
- [ ] Each detector fires on its positive fixture and does not fire on a
      similar-but-negative fixture.
- [ ] Scoring threshold is documented in `detection/scoring/README.md`.

## Tests required

`tests/unit/` per detector; `tests/integration/` for
`detector → lead`.

## Documentation requirements

`detection/rules/README.md`, `detection/scoring/README.md` updated.
