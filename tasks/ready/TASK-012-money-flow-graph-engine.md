# TASK-012: Money-flow graph engine

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** graph
- **depends_on:** TASK-001
- **human_authorization:** no

## Objective

Build the NetworkX-backed graph the money-flow detectors and the agent's tracing tools both run on: nodes for entities and accounts, edges for payments and transactions, each edge carrying amount, date and the source record id.

This is shared infrastructure. Keep the construction separate from any single analysis so fan-in, fan-out, cycles and pass-through can each be one small module on top (TASK-015..018).

## Allowed paths

```
detection/graph/__init__.py
detection/graph/builder.py
detection/graph/model.py
```

## Forbidden paths

```
frontend/**
agent/**
domain/schemas/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] A graph builds from canonical entities with no database access of its own -- it takes records, it does not fetch them.
- [ ] Every edge carries the source record id, so any path found can be traced back to evidence.
- [ ] Building the demo-scale graph is fast enough to do on request (document the measured time).
- [ ] Graph construction is deterministic: same records, same graph.

## Tests required

`tests/unit/` for construction from a known fixture; assert node/edge counts and edge provenance.

## Documentation requirements

Update `detection/graph/README.md` with the node/edge model.
