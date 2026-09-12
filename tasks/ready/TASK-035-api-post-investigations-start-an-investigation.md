# TASK-035: API: POST /investigations (start an investigation)

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032, TASK-021
- **human_authorization:** no

## Objective

Start an investigation from a lead: create the investigation record, kick off the bounded agent loop, and return immediately with the investigation id so the UI can subscribe to its event stream.

The request must not block for the whole investigation -- the demo watches it happen live.

## Allowed paths

```
backend/api/routes/investigations_start.py
```

## Forbidden paths

```
backend/api/main.py
frontend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] The endpoint returns before the investigation completes, with an id that is immediately queryable.
- [ ] Starting an investigation twice for the same lead is either rejected or returns the existing one -- documented either way, never two parallel runs on one lead.
- [ ] A failure to start is reported in the documented error shape, and leaves no half-created investigation.

## Tests required

`tests/integration/` for start, duplicate start, and start against an unknown lead.

## Documentation requirements

Update `backend/api/README.md`.
