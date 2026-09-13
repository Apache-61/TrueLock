# data/fixtures/

**Purpose:** small, committed datasets used by tests and local dev/demo
seeding — the safe, non-sensitive stand-in for `data/raw/`.

**Layout (Fase 3):**
- `cfdi/` — valid and invalid CFDI 4.0 XML samples
- `bank/` — bank CSV cycle, partial invalid rows, missing columns
- `efos/` — SAT 69-B snapshot rows (contextual only)
- `demo_scenario.json` — summary of the in-memory canonical scenario

**What does not go here:** real/sensitive data (→ `data/raw/`), or answer
keys (→ `data/answer_keys/`).

**Depends on:** `domain/schemas/` and `truelock.seeder.ingestion`.
