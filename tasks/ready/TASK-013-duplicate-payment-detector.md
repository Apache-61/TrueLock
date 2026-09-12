# TASK-013: Duplicate payment detector

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-004
- **human_authorization:** no

## Objective

Detect the same payment made more than once -- same beneficiary, near-identical amount, close in time, distinct payment records -- as a detector plugged into the TASK-004 registry.

Distinct from DUPLICATE_INVOICE: that one catches the same invoice billed twice, this one catches one invoice paid twice.

## Allowed paths

```
detection/rules/duplicate_payment.py
```

## Forbidden paths

```
detection/rules/base.py
frontend/**
agent/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] Fires on the duplicate-payment scenario and stays silent on clean background volume.
- [ ] The tolerance window (amount and date) is a documented, tunable parameter, not a magic number in the middle of the rule.
- [ ] A legitimate instalment schedule does not fire -- document how the rule distinguishes it.
- [ ] Every signal names the specific payment record ids involved.

## Tests required

`tests/unit/` for the rule; `tests/scenarios/` against the TASK-003 answer key.

## Documentation requirements

Add the rule to `docs/detection/rules.md`.
