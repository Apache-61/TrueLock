# TASK-014: Unusual amount detector

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-004
- **human_authorization:** no

## Objective

Flag amounts that are anomalous for the supplier or the category: round-number outliers, amounts just under an approval threshold, and statistical outliers against that supplier's own history.

Just-under-threshold is the highest-signal of the three in procurement fraud -- treat it as a first-class rule, not a footnote.

## Allowed paths

```
detection/rules/unusual_amount.py
```

## Forbidden paths

```
detection/rules/base.py
frontend/**
agent/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] Thresholds are configurable and documented, with the reasoning for the defaults.
- [ ] A supplier with a short history does not produce false outliers -- document the minimum sample size.
- [ ] Just-under-approval-threshold amounts are flagged as their own signal type.
- [ ] Every signal names the records and states the comparison that made the amount unusual.

## Tests required

`tests/unit/` covering each sub-rule; `tests/scenarios/` for precision on clean data.

## Documentation requirements

Add the rule to `docs/detection/rules.md`.
