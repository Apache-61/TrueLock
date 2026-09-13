# database/

**Purpose:** PostgreSQL schema and seed data — the persistence substrate
decided in `history/decisions/ADR-0001-stack.md`.

**What goes here:** `migrations/` (versioned SQL, starting with
`0001_init.sql`), `seeds/` (fixture-loading scripts/data for local dev and
demo). Apply migrations in filename order, then execute the seed scripts in
filename order.

**What does not go here:** ORM models (→ `domain/entities/`, which map
onto this schema but live separately), query logic (→
`backend/repositories/`).

**Depends on:** `domain/schemas/` (the schema here must stay consistent
with the JSON Schema contracts — a mismatch is a bug).

**Changing a migration that affects existing data requires human
authorization** (`CONTRIBUTING.md` §5).

**Owner:** Agent B (Data/Backend).

## Local database setup

```bash
for migration in database/migrations/*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"; done
for seed in database/seeds/*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$seed"; done
```

The migration and seed SQL is idempotent and may be re-run against the same
database. `0002_payment_transaction_ids.sql` is the forward migration for
the `Payment.transaction_ids` field added after the initial schema.
