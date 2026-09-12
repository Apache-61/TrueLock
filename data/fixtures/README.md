# data/fixtures/

**Purpose:** small, committed datasets used by tests and local dev/demo
seeding — the safe, non-sensitive stand-in for `data/raw/`.

**What goes here:** hand-curated or derived-and-anonymized records small
enough to review by eye, validating against `domain/schemas/`.

**What does not go here:** real/sensitive data of any volume (→ stays in
`data/raw/`, gitignored, never committed), generated fraud scenarios with
answer keys (→ `data/synthetic/` + `data/answer_keys/`).

**Depends on:** `domain/schemas/`.
