# TASK-039: API: POST /cases/{id}/questions (judge Q&A)

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-032, TASK-027
- **human_authorization:** no

## Objective

Expose the TASK-027 Q&A over HTTP: a question about a completed case, answered with citations to the evidence it rests on.

## Allowed paths

```
backend/api/routes/questions.py
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

- [ ] Answers include citations the UI can link to.
- [ ] Question length is bounded and over-long questions are rejected cleanly.
- [ ] A question against an incomplete case returns the documented 'not ready' response.
- [ ] Latency is bounded so the demo does not stall on a slow model call.

## Tests required

`tests/integration/` for a normal question, an over-long one, and an incomplete case.

## Documentation requirements

Update `backend/api/README.md`.
