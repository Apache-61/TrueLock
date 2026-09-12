# TASK-023: Structured agent outputs with schema validation

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-022
- **human_authorization:** no

## Objective

Make every model output the system acts on a validated structure, not prose: tool calls, findings, confidence, and the final conclusion.

A model returning malformed JSON is an expected condition, not an exception -- handle it with a bounded repair attempt and then a clean typed failure.

## Allowed paths

```
agent/runtime/structured.py
tests/**
```

## Forbidden paths

```
frontend/**
detection/**
database/**
agent/runtime/loop.py
```

## Acceptance criteria

- [ ] Malformed output is retried a bounded number of times, then fails cleanly with the raw text preserved for debugging.
- [ ] A validated output can never contain a tool name that is not in the registry.
- [ ] Confidence values are constrained to a documented range.
- [ ] Validation failures are recorded on the investigation step, not swallowed.

## Tests required

`tests/unit/` for valid output, malformed JSON, unknown tool name, and out-of-range confidence.

## Documentation requirements

Document the output contract in `agent/runtime/README.md`.
