# database/migrations/

**Purpose:** versioned, forward-only SQL migrations. `0001_init.sql` is
the initial schema mirroring `domain/schemas/`.

**What goes here:** `NNNN_description.sql` files, never edited once
applied anywhere — a change is a new migration.

**What does not go here:** seed/fixture data (→ `database/seeds/`).

**A migration that affects existing data requires human authorization**
(`CONTRIBUTING.md` §5).
