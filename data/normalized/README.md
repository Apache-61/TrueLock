# data/normalized/

**Purpose:** canonicalized records matching `domain/schemas/`, produced by
`scripts/ingest/` from `data/raw/`.

**What goes here:** output of the normalization pipeline — safe to
regenerate at any time from `data/raw/` + `scripts/ingest/`.

**What does not go here:** hand-curated test fixtures (→
`data/fixtures/`), synthetic scenarios (→ `data/synthetic/`).

**Depends on:** `domain/schemas/`, `scripts/ingest/`.
