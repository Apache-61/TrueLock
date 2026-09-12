# TASK-028: Agent tool: trace_outgoing_funds / trace_incoming_funds

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-005, TASK-012
- **human_authorization:** no

## Objective

Implement the fund-tracing tools from `docs/contracts/agent-tools.md` over the TASK-012 graph: from an account or entity, follow money out (or in) to a bounded depth, returning each hop with amount, date and the source record id.

This is the tool the money-trail UI renders and the one the agent leans on hardest. Depth must be bounded and the result must be traceable.

## Allowed paths

```
agent/tools/trace_funds.py
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

- [ ] Trace depth is a bounded parameter with a documented maximum.
- [ ] Every hop carries the source record id, so the UI can link to the underlying document.
- [ ] A cycle in the flow terminates the trace rather than looping.
- [ ] The result conforms to the `ToolResult` contract, including `execution_time` and `source_ids`.
- [ ] An entity with no outgoing flow returns an empty result, not an error.

## Tests required

`tests/unit/` on a hand-built graph: straight chain, branching, cycle, and empty cases.

## Documentation requirements

Update `agent/tools/README.md`.
