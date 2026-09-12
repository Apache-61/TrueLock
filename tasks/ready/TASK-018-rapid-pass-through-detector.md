# TASK-018: Rapid pass-through detector

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** graph
- **depends_on:** TASK-004, TASK-012
- **human_authorization:** no

## Objective

Detect accounts that receive and forward substantially the same amount within a short window while retaining little -- the signature of a conduit or shell account rather than a real operating business.

## Allowed paths

```
detection/graph/pass_through.py
detection/rules/pass_through.py
```

## Forbidden paths

```
detection/graph/builder.py
detection/rules/base.py
frontend/**
agent/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] The retention ratio and time window are documented, tunable parameters.
- [ ] A signal reports the in-edge, the out-edge, the elapsed time and the retained fraction.
- [ ] A normal business with fast supplier settlement does not fire -- document how it is excluded.

## Tests required

`tests/unit/` on hand-built flows; `tests/scenarios/` against the answer key.

## Documentation requirements

Add the rule to `docs/detection/rules.md`.
