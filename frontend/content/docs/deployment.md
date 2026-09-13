# Deployment

TrueLock demo/production-shaped deployment via Docker Compose.

## Profiles

| Command | What starts |
|---|---|
| `docker compose up -d postgres` | Database only (local pytest / migrate) |
| `docker compose --profile app up -d --build` | migrate → backend → frontend |

## Services

- **postgres** — Postgres 16, healthchecked; exposed to the host as `localhost:5433`
  (container port `5432`)
- **migrate** — applies SQL migrations + demo seed once
- **backend** — FastAPI on `:8000`, `/health` + `/ready`, provider pool from `config/agent-providers.json`
- **frontend** — Next.js on `:3000`, `NEXT_PUBLIC_API_URL` points at the API

## Environment

Copy `.env.example` → `.env`. Critical keys:

| Variable | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | DB password |
| `DATABASE_URL` | Backend persistence |
| `GEMINI_API_KEY` / `GEMINI_KEY_A`…`D` | Authorized Gemini projects |
| `HARD_BUDGET_STOP_USD` | Session hard stop (default 280) |
| `NEXT_PUBLIC_API_URL` | Browser → API base |
| `NEXT_PUBLIC_SITE_URL` | Canonical public origin (e.g. `https://truelockfa.tech`) |
| `FRONTEND_ORIGIN` | CORS allowlist (apex + automatic `www.` twin) |

Host `DATABASE_URL` (port **5433**):

```bash
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
```

Inside Compose, app services use `postgres:5432` on the container network.

Secrets stay in `.env` — never commit them (`SECURITY.md`).

## Health & readiness

- `GET /health` — process + Gemini routing status + observability counters
- `GET /ready` — DB healthy when `DATABASE_URL` is set; otherwise memory demo is ready
- `GET /api/metrics` — usage ledger, budgets, routing

Compose healthchecks probe `/ready` (backend) and `/` (frontend).

## What must never happen automatically

Per `CONTRIBUTING.md`, deploying to a shared demo host requires human
authorization — CI stays green but does not auto-deploy.

## Hosted `.tech` domain (judges need only a browser)

Production hostname used in configs: **`truelockfa.tech`**
(Tech Domains — DNS is case-insensitive).

| Piece | Target |
|---|---|
| Apex / `www` | Next.js frontend (Vercel) — includes `/docs` |
| `api.<domain>.tech` | FastAPI backend (Render) |
| Managed Postgres | Render Postgres → `DATABASE_URL` on the API |

### Checklist

1. Own/buy the `.tech` domain at your registrar.
2. Create Render Postgres + web service from [`render.yaml`](../render.yaml); set
   `GEMINI_*`, `FRONTEND_ORIGIN=https://truelockfa.tech`, run migrate/seed on release.
3. Deploy frontend on Vercel with **Root Directory = `frontend`**
   ([`frontend/vercel.json`](../frontend/vercel.json));
   set `NEXT_PUBLIC_API_URL=https://api.truelockfa.tech` and
   `NEXT_PUBLIC_SITE_URL=https://truelockfa.tech`.
4. DNS at the registrar:
   - `A` / `ALIAS` / `CNAME` for `@` and `www` → Vercel
   - `CNAME` `api` → Render hostname
5. Verify from a phone (no clone): `/docs`, `/health`, investigate, optional inject-fraud.

Detailed operator steps: [`docs/ops/hosted-tech-domain.md`](ops/hosted-tech-domain.md).

## Recovery

See `docs/ops/recovery-runbook.md`. Verify with:

```bash
PYTHONPATH=backend/src python scripts/verify_recovery.py
```

## Local without Compose frontend

```bash
# terminal 1
uvicorn truelock.api.app:app --reload --port 8000

# terminal 2
cd frontend && npm run sync-docs && npm run dev
```
