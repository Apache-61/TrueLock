# TrueLock Demo Walkthrough Script

A ~3–5 minute structured demonstration script for hackathon judges.
Full runbook: [`docs/demo/runbook.md`](demo/runbook.md). Judge index:
[`docs/challenge/README.md`](challenge/README.md).

---

## 1. Setup & Pre-Flight (15–30 seconds)

```bash
# Postgres (host port 5433)
docker compose up -d postgres
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'

# Terminal 1: Backend
uvicorn truelock.api.app:app --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

Open `http://localhost:3000`. Confirm API `http://localhost:8000/ready`.

---

## 2. Walkthrough Narrative (~2.5–4 minutes)

### Step 1: The Leads Dashboard
- **Speaker**: "Welcome to TrueLock. Rather than overwhelming auditors with raw anomaly tables, TrueLock runs deterministic fraud detectors across banking and CFDI records."
- **Point out**:
  - High-score circular / cycle leads (round-trip money flow).
  - Rapid pass-through leads (short time windows).
  - A control / low-score lead that should *not* become an accusation.
- **Key Message**: "Shared address or EFOS listing alone is contextual — not automatic proof."

### Step 2: Autonomous Bounded Investigation
- Click **Investigate** on a high-score lead (e.g. cycle / round-trip).
- **Speaker**: "The server-side Gemini agent gets the lead and picks from a strict allowlist of read-only forensic tools — it does not invent SQL or shell commands."
- **Point out the audit trail**: fund trace, counterparty inspect, exposure calculation.

### Step 3: Evidence Chain & Exposure Invariants
- **Speaker**: "Every finding is anchored to source records. Exposure uses unique root originating flows — we do not double-count edges in a cycle."
- Show evidence panel + net exposure vs naive edge sum.

### Step 4: Auditor & Judge Q&A
- Use the Judge Q&A input (`POST /api/cases/{case_id}/questions`).
- Ask: `"What evidence proves that the funds circulated back to the originating company?"`
- **Point out**: answers cite evidence / step IDs — not free-standing prose.

### Step 5 (optional, ~1 min): Inject hidden fraud
- Call or UI-trigger `POST /demo/inject-fraud` with `hidden_pass_through` (or `hidden_duplicate_payment`).
- **Speaker**: "Judges can inject an unseen pattern; detectors surface a lead and investigation follows the same protocol."
- Imports for raw files (when Postgres is up): `POST /api/imports/cfdi|bank|efos`.

---

## 3. Fallback Walkthrough (If Offline)

If Gemini quota or network drops:
- TrueLock engages the **deterministic fallback** path.
- Tools and calculations remain verified; the demo continues.
- Check health/metrics for provider / fallback status (`GET /health`, `GET /api/metrics`).
