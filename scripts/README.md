# scripts/

**Purpose:** operational scripts — not product code, not tests, but the
glue that runs both.

- `ingest/` — turn `data/raw/` into `data/normalized/`.
- `validate/` — schema/contract validation runnable outside pytest (used
  by CI and by hand).
- `demo/` — load a scenario, inject a hidden fraud pattern, reset between
  demo runs (`docs/demo/runbook.md`).
- `orchestration/` — the task claim/verify protocol and (later) worker
  adapters (`orchestrator/README.md`).
- `setup/` — one-time repo setup a human runs once (labels, branch
  protection) — see `PROJECT_STATE.md` → "Blocked" for why these are
  scripts rather than already applied.
