# orchestrator/policies/

**Purpose:** the rules the orchestrator (and any worker adapter) must
follow — provider pool/budget, usage-ledger shape, model-tier routing.

**What goes here:** `provider-pool.yaml` (the 4-project Gemini pool +
budget/failover rules), `usage-ledger.schema.json` (per-call cost
tracking shape). See `research/ai/README.md` §Model-tier routing for the
TIER 0-3 classification these policies should eventually encode.

**What does not go here:** the forensic agent's decision boundary (→
`agent/policies/` — a different, non-overlapping concern per
`ARCHITECTURE.md` §6/§57).

**Depends on:** `research/ai/README.md`, `.env.example`.
