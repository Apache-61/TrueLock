# TASK-042: Frontend: live agent events via SSE

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-038
- **human_authorization:** no

## Objective

Subscribe to the TASK-038 event stream and render the agent's work as it happens -- the single most persuasive thing the demo does. Watching the investigator reason in real time is what separates this from a report generator.

## Allowed paths

```
frontend/components/live-events/**
frontend/lib/sse.ts
tests/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Events appear as they arrive, without a page refresh.
- [ ] A dropped connection reconnects automatically and does not duplicate already-rendered events.
- [ ] The stream closing on completion is shown as completion, not as an error.
- [ ] An investigation that errors shows the failure rather than spinning forever.

## Tests required

Component tests against a stubbed event source: normal flow, reconnect, completion, and error.

## Documentation requirements

Update `frontend/README.md`.
