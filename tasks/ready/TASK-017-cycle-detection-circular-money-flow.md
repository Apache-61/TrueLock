# TASK-017: Cycle detection (circular money flow)

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** graph
- **depends_on:** TASK-004, TASK-012
- **human_authorization:** no

## Objective

Detect money returning to its origin through intermediaries -- the round-trip that distinguishes a kickback ring from ordinary trade -- by finding cycles in the TASK-012 graph.

## Allowed paths

```
detection/graph/cycles.py
detection/rules/cycles.py
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

- [ ] Cycles up to a documented maximum length are found; the bound exists so the search cannot blow up on the demo dataset.
- [ ] Cycle search completes within a documented time budget on the demo graph.
- [ ] A cycle signal reports the ordered path and the amount retained at each hop.
- [ ] Ordinary two-party back-and-forth trade is distinguished from a laundering cycle -- document the rule.

## Tests required

`tests/unit/` on graphs with known cycles and known acyclic cases; `tests/scenarios/` against the cycle answer key.

## Documentation requirements

Add the rule to `docs/detection/rules.md`.
