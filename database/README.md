# database/

**Purpose:** PostgreSQL schema and seed data — the persistence substrate
decided in `history/decisions/ADR-0001-stack.md`.

**What goes here:** `migrations/` (versioned SQL, starting with
`0001_init.sql`), `seeds/` (fixture-loading scripts/data for local dev and
demo).

**What does not go here:** ORM models (→ `domain/entities/`, which map
onto this schema but live separately), query logic (→
`backend/repositories/`).

**Depends on:** `domain/schemas/` (the schema here must stay consistent
with the JSON Schema contracts — a mismatch is a bug).

**Changing a migration that affects existing data requires human
authorization** (`CONTRIBUTING.md` §5).

**Owner:** Agent B (Data/Backend).
