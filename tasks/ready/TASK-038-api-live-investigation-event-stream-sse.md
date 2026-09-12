# TASK-038: API: live investigation event stream (SSE)

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032, TASK-024
- **human_authorization:** no

## Objective

Stream investigation events to the browser as they happen -- step started, tool called, evidence found, conclusion reached -- using Server-Sent Events.

SSE over WebSocket deliberately: the stream is one-directional and SSE reconnects on its own. This is what makes the demo feel live rather than like a page that eventually updates.

## Allowed paths

```
backend/api/routes/events.py
```

## Forbidden paths

```
backend/api/main.py
frontend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] A client subscribing mid-investigation receives subsequent events without needing the earlier ones.
- [ ] The stream terminates cleanly when the investigation finishes.
- [ ] A disconnected client does not leak a subscription or block the investigation.
- [ ] Event payload shapes are documented and match what TASK-024 records.
- [ ] The stream survives an investigation that errors -- it emits a failure event rather than hanging.

## Tests required

`tests/integration/` for subscribe, mid-stream subscribe, clean termination, and the error case.

## Documentation requirements

Document the event types in `backend/api/README.md` and `docs/integration-guide.md`.
