# Operational Scripts (`scripts/`)

Minimal, explicit entry points for seeding, executing, and verifying the TrueLock demo.

## Required CLI tools

Every contributor needs **`psql`** on `PATH`. Check with:

```bash
bash scripts/check_requirements.sh
```

Database shell scripts (`migrate.sh`, `seed_demo.sh`, `test_database.sh`) invoke `psql` directly and fail fast when it is missing.

## Scripts

- `check_requirements.sh` — Verifies `psql`, Python, and Node.js are installed.
- `migrate.sh` — Applies ordered SQL migrations (idempotent for canonical schema).
- `seed_demo.sh` — Loads `CASE-DEMO-001` once when absent.
- `test_database.sh` — Runs SQL invariant tests against the seeded demo.
- `seed_demo.py` — Seeds the canonical synthetic fraud scenario ($1,000,000 root transfer, $920,000 downstream hop, $740,000 kickback return) and the legitimate co-located supplier controls.
- `run_demo.py` — Runs the full end-to-end forensic investigation using Google Gemini (with deterministic fallback) and demonstrates evidence-grounded judge Q&A.
- `verify_demo.py` — Verifies all forensic invariants deterministically: cycle detection, root-flow exposure calculation (zero edge double-counting), provenance hashing, and legitimate control classification.

## Usage

```bash
# Verify CLI prerequisites
bash scripts/check_requirements.sh

# Initialize PostgreSQL (after docker compose up -d postgres)
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
bash scripts/migrate.sh
bash scripts/seed_demo.sh
bash scripts/test_database.sh

# Seed the in-memory demo dataset (no database required)
python scripts/seed_demo.py

# Run verification of all forensic rules and calculations
python scripts/verify_demo.py

# Run full end-to-end demo execution
python scripts/run_demo.py
```
