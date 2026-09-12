# TASK-037: API: GET /investigations/{id} with steps and evidence

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032, TASK-020
- **human_authorization:** no

## Objective

Serve one investigation's current state: status, the steps taken in order with the tool called and its result summary, the evidence gathered so far, and the decision log. Works for a running investigation as well as a finished one -- the timeline UI polls or streams this.

## Allowed paths

```
backend/api/routes/investigations.py
tests/**
```

## Forbidden paths

```
backend/api/main.py
frontend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Steps come back in the order they were recorded.
- [ ] A running investigation returns its partial state without error.
- [ ] Response shape matches `docs/contracts/api.md` and the `investigation_step` schema.
- [ ] An unknown investigation id returns the documented 404 shape.

## Tests required

`tests/integration/` for running, complete, and unknown investigations.

## Documentation requirements

Update `backend/api/README.md`.
