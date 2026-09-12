# TASK-015: Supplier concentration detector

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-004
- **human_authorization:** no

## Objective

Detect concentration risk: a supplier taking an outsized share of a buyer's spend, a supplier created shortly before winning volume, or a buyer whose spend is split across suppliers that share an address, phone or bank account.

## Allowed paths

```
detection/rules/supplier_concentration.py
tests/**
```

## Forbidden paths

```
detection/rules/base.py
frontend/**
agent/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] Concentration is measured over a documented window, not all-time.
- [ ] Shared-identity detection (address/phone/account) names which attribute matched.
- [ ] A genuinely single-supplier category does not fire -- document how.
- [ ] Every signal names the supplier and buyer record ids.

## Tests required

`tests/unit/` per sub-rule; `tests/scenarios/` against the answer key.

## Documentation requirements

Add the rule to `docs/detection/rules.md`.
