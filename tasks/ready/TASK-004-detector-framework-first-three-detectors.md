# TASK-004: Detector framework + first three detectors

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-001, TASK-003
- **human_authorization:** no

## Objective

Implement the detector interface (`docs/contracts/detector.md`), the registry, and the first three detectors: `DUPLICATE_INVOICE`, `INVOICE_PAYMENT_MISMATCH`, `69B_CORRELATION` (`docs/detection/rules.md`). Implement `detection/scoring/` to turn signals into `Lead`s with a documented, tunable threshold.

This task owns the framework every later detector plugs into, so keep the interface small and the registry open: a new detector must be addable as one new file plus one registry entry.

## Allowed paths

```
detection/rules/__init__.py
detection/rules/base.py
detection/rules/duplicate_invoice.py
detection/rules/invoice_payment_mismatch.py
detection/rules/efos_correlation.py
detection/scoring/**
```

## Forbidden paths

```
frontend/**
agent/**
domain/schemas/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] A detector is one class implementing the documented interface, registered in one place.
- [ ] Every signal carries the source record ids that justify it -- a signal with no provenance is a bug.
- [ ] Detectors are pure over their input: same input, same signals, no database or network access of their own.
- [ ] Each of the three detectors fires on its scenario from TASK-003 and stays silent on the clean background volume.
- [ ] `detection/scoring/` produces `Lead`s with a documented threshold and an explanation of why the lead scored as it did.

## Tests required

`tests/unit/` per detector for the rule logic; `tests/scenarios/` asserts each detector's findings against the TASK-003 answer keys (precision and recall, not just 'it ran').

## Documentation requirements

Update `detection/README.md` and `docs/detection/rules.md` with the implemented rules.
