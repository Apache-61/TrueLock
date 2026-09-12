# database/seeds/

**Purpose:** scripts/data to load `data/fixtures/` and `data/synthetic/`
scenarios into a fresh database for local dev and demo.

**What goes here:** idempotent loader scripts. Running a seed twice should
not duplicate data or error.

**What does not go here:** the fixture data itself (→ `data/fixtures/`,
`data/synthetic/`) — this directory only loads it.

**Depends on:** `database/migrations/0001_init.sql`, `data/fixtures/`.
