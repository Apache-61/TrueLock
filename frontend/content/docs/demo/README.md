# Demo docs

Judge-facing demo material for TrueLock.

## Start

1. Challenge index: [`docs/challenge/README.md`](../challenge/README.md)
2. **Runbook (5-minute path):** [`runbook.md`](runbook.md)
3. Spoken script: [`docs/demo-script.md`](../demo-script.md)
4. API contract: [`docs/contracts/api.md`](../contracts/api.md)

## Commands

```bash
# Postgres on host port 5433
docker compose up -d postgres
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'

# Optional full stack
docker compose --profile app up -d --build

# Or API + UI locally
uvicorn truelock.api.app:app --reload --port 8000   # from repo with PYTHONPATH/backend install
cd frontend && npm run dev                          # http://localhost:3000
```

Verification helpers:

```bash
python scripts/verify_demo.py
python scripts/run_demo.py
```

Hidden fraud for judges: `POST /demo/inject-fraud` (see runbook + API contract).
Scenario answer keys under `data/answer_keys/` are for team checks only — never
exposed to the agent or UI.
