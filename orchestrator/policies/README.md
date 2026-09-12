# orchestrator/policies/

**Purpose:** the rules the orchestrator and every worker adapter must
follow — provider pool/budget, usage-ledger shape, handoff shape.

**What is here:**

| File | What it fixes |
|---|---|
| `provider-pool.yaml` | the 4-project Gemini pool, budgets, failover rules |
| `usage-ledger.schema.json` | one row per model API call, for cost tracking |
| `task-result.schema.json` | the AI-to-AI handoff every task execution emits |

`task-result.schema.json` is the machine-readable form of the handoff
format in `orchestrator/README.md`. It is validated in
`tests/contract/test_orchestrator_contracts.py` against the objects the
worker actually emits, so the schema and the code cannot drift apart
silently.

See `research/ai/README.md` §Model-tier routing for the TIER 0-3
classification these policies should eventually encode.

**What does not go here:** the forensic agent's decision boundary (→
`agent/policies/` — a different, non-overlapping concern per
`ARCHITECTURE.md` §6/§57).

**Depends on:** `research/ai/README.md`, `.env.example`.
