# Contract: Frontend/Backend API

Backend: FastAPI. Consumed by `frontend/`. Until the backend is
implemented, the frontend builds against a mock returning fixtures shaped
exactly like these responses (`frontend/README.md`).

## Endpoints (draft — refine during `TASK-006`)

```
GET  /cases                    -> Case[] (summary view)
GET  /cases/:id                -> Case
GET  /investigations/:lead_id  -> InvestigationStep[]
GET  /graph/:case_id           -> { nodes: Entity[], edges: Edge[] }
GET  /evidence/:id             -> Evidence
GET  /events?case_id=          -> ObservabilityEvent[]  (see docs/contracts below)
POST /questions                -> { question: string } -> { answer: string, evidence_refs: string[] }
POST /demo/inject-fraud        -> { scenario_id?: string } -> { entity_id: string }  (judge control, see docs/demo/runbook.md)
```

## Observability event shape

Rendered as the live timeline in `docs/demo/runbook.md` step 4 /
`ARCHITECTURE.md` "Observability":

```json
{ "timestamp": "2026-08-13T14:03:16Z", "case_id": "CASE-001", "message": "Tracing payment TX-8821", "step_id": "I-004" }
```

Human-readable `message`, plus a `step_id` the frontend can use to fetch
the full `InvestigationStep` if the user clicks in.

## Rules

- Every response type here corresponds 1:1 to a schema in
  `domain/schemas/` — the API does not invent shapes the domain model
  doesn't have.
- `POST /questions` must answer using retrievable evidence/investigation
  steps (`evidence_refs`), never free-standing prose with no backing IDs —
  this is what makes the Q&A demo step (`docs/demo/runbook.md` step 10)
  auditable rather than a chatbot answer.
- `POST /demo/inject-fraud` exists specifically so judges can hide a new
  fraud pattern and watch the system find it (`docs/demo/runbook.md`).

## Who owns this contract

Agent B (Data/Backend) implements the server side; Agent A (Frontend)
consumes it and may propose changes but needs Agent B's/human sign-off to
change the shape (`CONTRIBUTING.md` §5 covers contract changes broadly).
