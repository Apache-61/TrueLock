# TASK-005: Agent tool layer + tool schemas

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-009
- **human_authorization:** no

## Objective

Implement the read-only tool layer from `docs/contracts/agent-tools.md`: the `ToolResult` contract (`result`/`provenance`/`source_ids`/`execution_time`/`errors`), the tool registry, the machine-readable tool schemas the model is given, and the first two concrete tools (`get_entity_profile`, `list_leads`).

Remaining tools are separate tasks that plug into this layer. Tools read through `backend/repositories/` -- they never reshape the database.

## Allowed paths

```
agent/tools/__init__.py
agent/tools/base.py
agent/tools/schemas.py
agent/tools/registry.py
agent/tools/entity_profile.py
agent/tools/leads.py
tests/**
```

## Forbidden paths

```
database/**
frontend/**
detection/**
domain/schemas/**
```

## Acceptance criteria

- [ ] Every tool returns the documented `ToolResult` shape, including on error -- a failing tool returns an error result, it does not raise into the agent loop.
- [ ] Every tool result carries `source_ids` that trace back to real records.
- [ ] Tool schemas are generated from the tool definitions, so a schema cannot drift from the function it describes.
- [ ] Tools are read-only: no tool writes to the database.
- [ ] A tool that would return an unbounded result set paginates or caps, and says so in the result.

## Tests required

`tests/unit/` for the registry and the `ToolResult` contract; `tests/contract/` asserts every registered tool's schema matches its signature.

## Documentation requirements

Update `agent/tools/README.md` with the implemented tools and how to add one.
