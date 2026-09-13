# Traceability matrix — gap → contract → module → test → scenario

Source plan: `docs/challenge/plan-agente-consultoria.md` (Fases 0–7).  
Updated: 2026-09-13.

Review order: start with the [five-minute judge path](README.md), then use
this matrix to trace each claimed capability to its contract, implementation,
test, and scenario.

| Gap / phase | Contract / docs | Module | Test | Scenario / fixture |
|-------------|-----------------|--------|------|--------------------|
| P2.5 docs baseline | `docs/testing.md`, `docs/contracts/*` | — | `tests/contract/test_schemas.py` | — |
| P1.1 case from evidence | `docs/contracts/investigation.md` | `services/investigation_service.py`, `agent/investigator.py` | `tests/unit/test_agent.py`, `tests/e2e/test_investigation_flow.py` | demo seed, cycle fixtures |
| P1.2 / tools protocol | `docs/contracts/agent-tools.md`, `docs/investigation/protocol.md` | `agent/tools.py` | `tests/contract/test_agent_tools.py` | allowlisted tools |
| Fase 2 import pipeline | `docs/contracts/api.md` (`/api/imports/*`) | `services/import_service.py`, `seeder/ingestion/*` | `tests/unit/test_import_pipeline.py`, `tests/integration/test_database.py` | `data/fixtures/{cfdi,bank,efos}` |
| Fase 3 persistence | migrations `0003`–`0008`, `database/README.md` | `database/repositories/postgres.py` | `tests/integration/test_database.py`, `database/tests/001_demo_invariants.sql` | `database/seeds/001_demo.sql` |
| Fase 4 demo UX | `docs/contracts/api.md`, `docs/demo/runbook.md` | `demo_injection_service.py`, `presenters.py`, frontend panels | `tests/contract/test_api_contract.py`, `frontend/__tests__/investigationUi.test.mjs` | `hidden_pass_through`, `hidden_duplicate_payment` |
| Fase 5 detectors | `docs/detection/rules.md`, answer keys | `detection/rules/*`, `detection/scoring/*` | `tests/unit/test_*detector*`, scenario seeds | `data/answer_keys/*`, `data/fixtures/bank/valid_cycle.csv` |
| Fase 6 policy / eval | `agent/policy/v1.md`, `data/eval_corpus/README.md` | `agent/eval/*`, `scripts/eval_agent.py` | `tests/e2e/*`, CI promotion gate | `data/eval_corpus/{train,eval}/*` |
| Fase 7 ops | `docs/ops/recovery-runbook.md`, Compose health | `provider_router.py`, `usage_ledger.py` | `scripts/verify_recovery.py`, CI compose | provider failover budgets |
| Money trail UI | `GET /api/graph/{case_id}` | `MoneyTrailGraph.tsx` | `test_memory_graph_for_case`, frontend build | demo graph nodes/edges |
| Browser smoke | — | Playwright `frontend/e2e` | `npm run test:e2e` (opt-in) | live API + Next |

## Explicit deferrals (not gaps for this cut)

- Fine-tuning / custom model weights
- NetworkX / Solana analytics
- Full 14-tool catalogue beyond the allowlisted protocol set
