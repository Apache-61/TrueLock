# Demo runbook

Target **~5-minute** judge flow (core narrative fits in ~3 minutes; buffer for
Q&A and inject-fraud). Pair with [`docs/demo-script.md`](../demo-script.md).

## Preconditions

| Item | Value |
|------|--------|
| Frontend | `http://localhost:3000` |
| API | `http://localhost:8000` |
| Postgres (host) | **`localhost:5433`** (`5433:5432` in Compose) |
| Env template | `.env.example` → `.env` (never commit `.env`) |

```bash
docker compose up -d postgres
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
# Prefer Compose migrate+seed on Windows:
docker compose --profile app run --rm migrate
# API
uvicorn truelock.api.app:app --reload --port 8000
# UI
cd frontend && npm run dev
```

Quick checks: `GET /health`, `GET /ready`, OpenAPI at `/docs`.

## Steps (on-stage)

1. **Open the dashboard** — leads with risk scores and detector signals.
2. **"I am investigating this because…"** — show lead reason / signals before tools run.
3. **Start investigation** — `POST /api/investigations/start` (UI: Investigate).
4. **Agent tools (visible)** — allowlisted forensic tools only
   (`docs/contracts/agent-tools.md`).
5. **Graph / money trail** — `GET /api/graph/{case_id}`; Invoice → Payment → Account → Entity.
6. **Evidence accumulates** — each item cites source records
   (`docs/contracts/evidence.md`).
7. **Discarded lead** — at least one alternative with a discard reason (required beat).
8. **Case file** — hypothesis, amount, entities, evidence, discarded leads, limitations
   (`docs/contracts/case.md`).
9. **Judge Q&A** — `POST /api/cases/{case_id}/questions` grounded in evidence IDs
   (`docs/investigation/protocol.md`).
10. **Optional: inject fraud** — see below; watch a new lead appear and investigate.

## The hidden-fraud moment

Judges introduce a pattern without hand-tuning for that exact case:

```http
POST /demo/inject-fraud
Content-Type: application/json

{ "scenario_id": "hidden_pass_through" }
```

Also available: `hidden_duplicate_payment`. Contract:
[`docs/contracts/api.md`](../contracts/api.md). Answer keys in `data/answer_keys/`
are team-only (not served to agent or frontend).

Related: import pipeline for fixtures —

- `POST /api/imports/cfdi`
- `POST /api/imports/bank`
- `POST /api/imports/efos`

(Postgres required; sample files under `data/fixtures/`.)

## Failure handling

If Gemini is unreachable, the server falls back to a deterministic investigation
path so the demo continues (`docs/architecture.md`, `docs/ops/recovery-runbook.md`).
Verify with `python scripts/verify_recovery.py` before the live session — not during it.

## Pre-demo checklist

- [ ] `DATABASE_URL` uses host port **5433**
- [ ] `/health` and `/ready` OK; UI loads leads
- [ ] Inject scenario prepared; answer key not in agent path
- [ ] Money-flow / evidence chain render on demo data
- [ ] At least one discarded lead visible
- [ ] Q&A tested (why investigate / how much / what would change)
- [ ] Gemini fallback / provider failover smoke-tested
- [ ] Clean environment (reset if needed: `POST /api/scenarios/reset` for in-memory demo)
