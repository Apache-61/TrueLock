# database/

**Purpose:** PostgreSQL schema and seed data — the persistence substrate
decided in `history/decisions/ADR-0001-stack.md`.

**What goes here:** `migrations/` (versioned SQL) and `seeds/` (an explicit
local/demo fixture). Migrations `0003`–`0007` establish the canonical
`truelock` schema used by the application; the earlier public tables remain
only as a forward-compatible legacy path.

**What does not go here:** query logic. Parameterized PostgreSQL repositories
live in `backend/src/truelock/database/repositories/postgres.py`.

**Depends on:** `domain/schemas/` (the schema here must stay consistent
with the JSON Schema contracts — a mismatch is a bug).

**Changing a migration that affects existing data requires human
authorization** (`CONTRIBUTING.md` §5).

**Owner:** Agent B (Data/Backend).

## Requirements

- **`psql`** on `PATH` (PostgreSQL client). Verify with `bash scripts/check_requirements.sh`.
- A running PostgreSQL 16+ instance (`docker compose up -d postgres` is the default local path).

## Local database setup

```bash
bash scripts/check_requirements.sh
docker compose up -d postgres
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5432/truelock'
bash scripts/migrate.sh
bash scripts/seed_demo.sh
bash scripts/test_database.sh
```

The runner records canonical migrations and skips already-applied files. The
seed runs only when `CASE-DEMO-001` is absent; it is never loaded
automatically by Docker Compose or the backend.
