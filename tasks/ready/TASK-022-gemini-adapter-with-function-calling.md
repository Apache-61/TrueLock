# TASK-022: Gemini adapter with function calling

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-005
- **human_authorization:** no

## Objective

Implement the Gemini client behind a narrow interface the agent loop depends on: send a prompt plus the TASK-005 tool schemas, get back either a tool call or a final answer.

Route through `orchestrator/routing/` so spend lands in the usage ledger and a key switch is logged as a `ROUTING_EVENT` -- the budget is ~USD 300 across four projects and untracked spend is how that disappears.

## Allowed paths

```
agent/runtime/gemini.py
agent/runtime/model.py
```

## Forbidden paths

```
frontend/**
detection/**
database/**
agent/runtime/loop.py
```

## Acceptance criteria

- [ ] Tool schemas from TASK-005 are passed as function declarations without a second hand-maintained copy.
- [ ] Every call records usage (tokens, model, estimated cost) in the existing usage ledger.
- [ ] A rate-limit or transient error is retried with backoff a bounded number of times, then surfaces as a typed error.
- [ ] The model identifier is configurable; no model name is hard-coded in the loop.
- [ ] The adapter is unit-testable without network access.

## Tests required

`tests/unit/` against a stubbed transport: tool-call parsing, final-answer parsing, retry/backoff, and ledger recording.

## Documentation requirements

Update `agent/runtime/README.md` with configuration and the env vars required.
