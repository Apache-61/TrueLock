# Operational Scripts (`scripts/`)

Minimal, explicit entry points for seeding, executing, and verifying the TrueLock demo.

- `seed_demo.py` — Seeds the canonical synthetic fraud scenario ($1,000,000 root transfer, $920,000 downstream hop, $740,000 kickback return) and the legitimate co-located supplier controls.
- `run_demo.py` — Runs the full end-to-end forensic investigation using Google Gemini (with deterministic fallback) and demonstrates evidence-grounded judge Q&A.
- `verify_demo.py` — Verifies all forensic invariants deterministically: cycle detection, root-flow exposure calculation (zero edge double-counting), provenance hashing, and legitimate control classification.

## Usage

```bash
# Seed the demo dataset
python scripts/seed_demo.py

# Run verification of all forensic rules and calculations
python scripts/verify_demo.py

# Run full end-to-end demo execution
python scripts/run_demo.py
```
