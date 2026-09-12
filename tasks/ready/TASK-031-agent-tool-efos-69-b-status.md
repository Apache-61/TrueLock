# TASK-031: Agent tool: EFOS / 69-B status check

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-005, TASK-011
- **human_authorization:** no

## Objective

Expose the TASK-011 EFOS lookup as an agent tool: given an RFC, return the 69-B listing status, the date it applied, and the provenance of the snapshot the answer came from.

## Allowed paths

```
agent/tools/efos.py
tests/**
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

- [ ] The result states the snapshot date, so a stale answer is visible as stale.
- [ ] An unlisted RFC returns 'not listed' as a normal result.
- [ ] Conforms to the `ToolResult` contract.

## Tests required

`tests/unit/` for listed, unlisted, and malformed RFC.

## Documentation requirements

Update `agent/tools/README.md`.
