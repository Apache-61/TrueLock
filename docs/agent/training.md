# Agent training & promotion

## Policy

Versioned instructions live in `backend/src/truelock/agent/policy/`:

- `v1.md` — when to FOLLOW / DISCARD / ESCALATE / CONCLUDE
- `few_shot_v1.json` — structured high-quality step examples

`ForensicInvestigator` loads policy `v1` into the system instruction and
records `policy_version`, `tool_contract_version`, and `model` on each case
(`limitations` + `citations`).

## Splits

| Split | Location | Rule |
|---|---|---|
| Train | `data/eval_corpus/train/` | Practice / few-shot inspiration; different entities |
| Eval (blocked) | `data/eval_corpus/eval/` | Promotion gate; never train on these entity IDs |

## Evaluation metrics

Implemented in `truelock.agent.eval.metrics`:

- argument validity rate
- repeated tool calls
- source coverage vs expected trail
- terminal decision match
- exposure accuracy
- invented sources (TX-/PMT- not in dataset)
- Q&A `evidence_refs` when required
- investigation length
- control / EFOS-only must not substantiate

Thresholds: `backend/src/truelock/agent/eval/thresholds.json`.

## Training loop

```bash
# Optional: copy .env.example → .env and set GEMINI_API_KEY / GEMINI_KEY_A..D
PYTHONPATH=backend/src python scripts/train_agent_live.py
PYTHONPATH=backend/src python scripts/eval_agent.py
```

Appends JSONL rows to `docs/agent/training-log.jsonl`. Without API keys the
loop runs in `offline-fallback` mode (deterministic investigator) but still
enforces the blocked eval gate.

## Promotion

A policy/prompt/model change promotes only if the blocked eval set passes.
Fine-tuning is deferred until legal/privacy review and a demonstrated gain
over prompt + tools.

### Promoted combo (hackathon freeze)

| Field | Value |
|---|---|
| policy_version | `v1` |
| few_shot | `few_shot_v1.json` (cycle, pass-through, duplicate, control, 69-B) |
| model default | `gemini-2.5-flash` (`GEMINI_MODEL`) |
| thresholds | `backend/src/truelock/agent/eval/thresholds.json` |
| eval_seed | `fase6-eval-2026-09` |
| offline gate | `PROMOTION GATE PASSED` |
| live keys | configure `.env` then re-run `train_agent_live.py` |

### Iteration log (Phase 2)

| When | Mode | Change | Gate |
|---|---|---|---|
| 2026-09-13 | offline | Expanded train corpus + dataset factories; few-shot pass-through/duplicate/69-B; policy minimum-evidence rows | PASS |
| 2026-09-13 | offline | Soft gates on inject train packs pending live Gemini | PASS |
| 2026-09-13 | offline | Phase 3 freeze: e2e + eval + verify_demo green; no Gemini keys in env | PASS |

To upgrade from offline to live Gemini: copy `.env.example` → `.env`, set
`GEMINI_API_KEY` (or `GEMINI_KEY_A..D`), then:

```bash
PYTHONPATH=backend/src python scripts/train_agent_live.py
```

## E2E gate

`tests/e2e/` covers dataset → detector → agent → case → API, inject+offline,
and the promotion gate. Postgres path skips without `DATABASE_URL`.
