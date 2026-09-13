# Contract: Frontend/Backend API

Backend: FastAPI (`backend/src/truelock/api/app.py`). Consumed by
`frontend/lib/api.ts`. Version **0.3.0**.

## Endpoints

```
GET  /health
GET  /ready
GET  /api/metrics

GET  /api/leads                         -> Lead[]
GET  /api/leads/{lead_id}               -> Lead
GET  /api/cases                         -> Case[] (summary)
GET  /api/cases/{case_id}               -> Case
POST /api/investigations/start          -> { lead_id } -> InvestigationBundle
GET  /api/investigations/{case_id}      -> InvestigationBundle
GET  /api/graph/{case_id}               -> { case_id, nodes: Entity[], edges: Edge[] }
GET  /api/cases/{case_id}/findings      -> Finding[]
GET  /api/evidence/{evidence_id}        -> Evidence
GET  /api/events?case_id=               -> ObservabilityEvent[]
POST /api/cases/{case_id}/questions     -> { question } -> QAResponse

POST /api/imports/cfdi                  -> multipart file -> ImportReport  (Postgres required)
POST /api/imports/bank                  -> multipart file -> ImportReport  (Postgres required)
POST /api/imports/efos                  -> multipart file -> ImportReport  (Postgres required; context only)

GET  /api/demo/scenarios                -> { scenario_id, description }[]
POST /demo/inject-fraud                 -> { scenario_id? } -> InjectResult
POST /api/demo/clear-analysis           -> empty workspace (no leads)
POST /api/demo/load-demo                -> seed CASE-DEMO-001 + detector leads
POST /api/scenarios/reset               -> same as clear-analysis
```

`POST /api/demo/clear-analysis` wipes threads/investigations/evidence/imports and
leaves an empty `CASE-DEMO-001` shell with **no leads**.

`POST /api/demo/load-demo` reseeds the canonical demo and runs detectors so leads appear.

Uploads via `/api/imports/*` also re-run detectors after accept.

### InvestigationBundle

```json
{
  "case": { "case_id": "...", "discarded_leads": [...] },
  "steps": [ { "step_id": "...", "tool": "...", "reason": "...", "status": "..." } ],
  "evidence": [ { "evidence_id": "...", "kind": "...", "summary": "..." } ]
}
```

### QAResponse

```json
{
  "answer": "string",
  "evidence_refs": ["EV-001", "EV-002"],
  "investigation_step_ids": ["I-001"]
}
```

When the case has no retrievable evidence, `answer` states insufficiency and
`evidence_refs` is an empty array.

### InjectResult

```json
{
  "scenario_id": "hidden_pass_through",
  "description": "...",
  "entity_id": "ENT-HIDDEN-VENDOR-001",
  "lead_id": "LEAD-...",
  "lead_count": 5,
  "message": "..."
}
```

Available scenarios: `hidden_pass_through`, `hidden_duplicate_payment`.
Answer keys for judges live under `data/answer_keys/` and are never exposed to
the agent runtime.

### Observability event shape

Rendered as the live timeline in `docs/demo/runbook.md`:

```json
{
  "timestamp": "2026-08-13T14:03:16Z",
  "case_id": "CASE-001",
  "message": "Tracing payment TX-8821",
  "event_type": "investigation_step",
  "step_id": "I-004"
}
```

Human-readable `message`, plus optional `step_id` the frontend can use to
fetch the full investigation step when the user clicks in the timeline.

## Rules

- Every response type corresponds to a schema in `domain/schemas/` — the API
  does not invent shapes the domain model doesn't have.
- `POST /api/cases/{case_id}/questions` must answer using retrievable
  evidence and investigation steps (`evidence_refs`), never free-standing
  prose with no backing IDs.
- `POST /demo/inject-fraud` lets judges introduce a hidden fraud pattern and
  watch detectors surface it (`docs/demo/runbook.md`).
- `GET /api/graph/{case_id}` returns nodes and edges for the selected case,
  not a static fixture.

## Ownership

Backend API subsystem implements the server side; frontend consumes it.
Contract changes follow team review conventions in `CONTRIBUTING.md`.
