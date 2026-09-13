# Recovery runbook (Fase 7)

Executable checks live in `scripts/verify_recovery.py`. Run after any
infra change or before a demo:

```bash
PYTHONPATH=backend/src python scripts/verify_recovery.py
```

## 1. Process / container restart

1. `docker compose --profile app up -d`
2. Confirm `GET /ready` → `{"status":"ready"}`
3. Confirm `GET /health` shows `database.status=ok` when Postgres is used
4. Re-open a prior case via `GET /api/investigations/{case_id}` — steps and
   evidence must still load from PostgreSQL (not wiped by backend restart)
5. Live events for new investigations are dual-written to memory +
   `truelock.operational_events` (external_case_key)

## 2. Provider failure / failover

1. Configure at least two keys (`GEMINI_KEY_A`, `GEMINI_KEY_B`) or leave both
   empty for offline deterministic mode
2. On HTTP 429 / 5xx the router marks the provider failed and emits
   `ROUTING_EVENT {from,to,reason}` (visible under `GET /api/metrics` and
   `GET /api/events?case_id=OPS`)
3. When no healthy provider remains, Gemini returns offline fallback; the
   investigator continues with the deterministic tool plan

## 3. Hard budget stop

1. Session spend is tracked in the usage ledger
2. When spend ≥ `hard_budget_stop_usd` (default 280), the client refuses new
   model calls and falls back offline — the agent cannot exceed the budget
3. Step/time budgets (`MAX_INVESTIGATION_STEPS` / `MAX_INVESTIGATION_SECONDS`)
   still force `ESCALATE` independently

## 4. Concurrent investigations

1. Concurrent `POST /api/investigations/start` for the **same** lead is
   serialized by an in-process lock
2. With Postgres, identical lead + dataset fingerprint returns the persisted
   investigation (idempotent)

## 5. Frontend / UI errors

1. Lead load and investigate failures surface as visible error banners
2. Q&A without evidence shows insufficiency + empty evidence refs

## 6. Database recovery

```bash
docker compose up -d postgres
bash scripts/migrate.sh
bash scripts/seed_demo.sh
bash scripts/test_database.sh
```

If migrations fail midway, fix forward-only — do not rewrite applied files.
