# Agent evaluation corpus (Fase 6 / training plan)

Packs used to evaluate investigator behaviour. **Never imported by agent
runtime code** except via the offline eval harness (`truelock.agent.eval`).

## Splits

| Split | Path | Purpose |
|---|---|---|
| **eval** (blocked) | `eval/` | Promotion gate — must pass after any policy/prompt/model change |
| **train** | `train/` | Practice / live iteration — different entities than eval |

Do not place variants of the same cycle entity in both splits.

Each pack includes: `input_lead`, `allowed_tools`, `expected_trail`,
`minimum_evidence`, `expected_terminal_decision`, `audit_questions`.
Optional `dataset` keys load factories from `truelock.agent.eval`
(`cycle_dedup`, `pass_through_temporal_positive`, inject scenarios, etc.).

## Coverage (training plan)

| Scheme | Train | Eval (blocked) |
|---|---|---|
| Round-trip / cycle | `train/cycle_dedup_alt.json` | `eval/round_trip_cycle_p0.json` |
| Pass-through | `train/pass_through_temporal.json`, `train/hidden_pass_through.json` | — |
| Duplicate payment | `train/duplicate_payment.json` | — |
| Shared-address control | — | `eval/shared_address_control.json` |
| EFOS contextual | `train/shell_company_context.json` | `eval/efos_contextual_only.json` |
| Concentration / timing | `train/concentration_risk_control.json`, `train/unusual_timing_control.json` | — |

Run:

```bash
PYTHONPATH=backend/src python scripts/eval_agent.py
PYTHONPATH=backend/src python scripts/train_agent_live.py
PYTHONPATH=backend/src pytest -q tests/e2e/
```
