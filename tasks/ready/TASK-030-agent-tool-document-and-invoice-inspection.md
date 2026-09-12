# TASK-030: Agent tool: document and invoice inspection

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-005
- **human_authorization:** no

## Objective

Implement the tools that let the agent read the underlying documents: fetch an invoice with its line items, fetch a payment with its complement, and compare two invoices field by field.

## Allowed paths

```
agent/tools/documents.py
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

- [ ] Comparison returns a field-level diff, not a prose summary -- the model should reason over the diff.
- [ ] A missing document returns an error result, not an exception.
- [ ] Results conform to the `ToolResult` contract with source ids.

## Tests required

`tests/unit/` for fetch, compare-identical, compare-different, and missing-document.

## Documentation requirements

Update `agent/tools/README.md`.
