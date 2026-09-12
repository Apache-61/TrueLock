# TASK-029: Agent tool: relationship and counterparty analysis

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-005, TASK-012
- **human_authorization:** no

## Objective

Implement the relationship tools: who does this entity transact with, which counterparties are shared with another entity, and which identity attributes (address, phone, bank account, legal representative) are shared across entities.

## Allowed paths

```
agent/tools/relationships.py
```

## Forbidden paths

```
agent/tools/base.py
agent/tools/registry.py
frontend/**
database/**
detection/**
```

## Acceptance criteria

- [ ] Shared-attribute results name which attribute matched and its value's source record.
- [ ] Results are capped and the cap is reported in the result.
- [ ] The tool conforms to the `ToolResult` contract.
- [ ] An entity with no relationships returns an empty result, not an error.

## Tests required

`tests/unit/` for each relationship type against a fixture.

## Documentation requirements

Update `agent/tools/README.md`.
