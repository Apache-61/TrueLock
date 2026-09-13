# TrueLock Demo Walkthrough Script

A 3-minute structured demonstration script for hackathon judges.

---

## 1. Setup & Pre-Flight (15 seconds)

Ensure services are running:
```bash
# Terminal 1: Backend
uvicorn truelock.api.app:app --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```
Open `http://localhost:3000` in the browser.

---

## 2. Walkthrough Narrative (2.5 minutes)

### Step 1: The Leads Dashboard
- **Speaker**: "Welcome to TrueLock. Rather than overwhelming auditors with raw anomaly tables, TrueLock runs deterministic fraud detectors across banking and CFDI records."
- **Point out**:
  - `LEAD-CYCLE-TX-ROOT-001` (Score: 0.98): Round-trip circular money flow.
  - `LEAD-PASSTHROUGH-...` (Score: 0.88): Rapid pass-through (<2 hours).
  - `LEAD-CONTROL-SHARED-ADDRESS` (Score: 0.35): Legitimate suppliers co-located at Av. Reforma 222.
- **Key Message**: "Notice the control lead: TrueLock knows two vendors sharing a building address is not fraud."

### Step 2: Autonomous Bounded Investigation
- Click **"Investigate Lead"** on `LEAD-CYCLE-TX-ROOT-001`.
- **Speaker**: "When we launch the investigation, our server-side Google Gemini agent receives the lead and formulates a working hypothesis. It does not guess answers; it chooses from a strict allowlist of read-only forensic tools."
- **Point out "What the Auditor Did"**:
  1. `TRACE_OUTGOING_FUNDS`: Traced from company account `...0001` through vendor `...0002` to shell `...0003`.
  2. `INSPECT_COUNTERPARTIES`: Verified entity profiles and detected EFOS DEFINITIVE status on Logística Fantasma.
  3. `CALCULATE_EXPOSURE`: Computed root-flow exposure with circular return offset.

### Step 3: Evidence Chain & Exposure Invariants
- **Speaker**: "Look at the Evidence Panel. Every finding is anchored by a cryptographic hash of the underlying source record. More importantly, look at the exposure calculation:
  - Root disbursement: **$1,000,000 MXN**
  - Returned to origin: **$740,000 MXN**
  - Net exposure: **$260,000 MXN**
  TrueLock avoids the classic mistake of summing graph edges ($2.66M MXN), preventing double-counting of circulated capital."

### Step 4: Auditor & Judge Q&A
- Navigate to the **Judge Q&A Assistant** input.
- Enter question: `"What evidence proves that the funds circulated back to the originating company?"`
- Click **"Ask Auditor"**.
- **Point out**: Gemini cites specific evidence IDs (`[EVD-...]`) and transaction records without hallucinating outside the audited case file.

---

## 3. Fallback Walkthrough (If Offline)

If Google Gemini API quota or network connectivity drops during the pitch:
- TrueLock detects the condition automatically and engages the **Deterministic Fallback Engine**.
- All tools execute, findings are substantiated, and calculations remain 100% verified.
- The UI status indicator will show `Gemini: ● fallback-deterministic`.
