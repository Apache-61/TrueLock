# data/answer_keys/

**Purpose:** expected outputs for fixtures and synthetic scenarios — used
**only** by tests and humans scoring a demo, never by runtime agent code.

**What goes here:**
- `demo_scenario_answer_key.json` — canonical `$1M → $920k → $740k` cycle
- `cfdi_valid_answer_key.json`, `bank_cycle_answer_key.json`,
  `efos_69b_answer_key.json` — Fase 3 import fixture expectations
- `hidden_pass_through_answer_key.json` — judge injection (Fase 4)
- Detector regression keys (Fase 5): `duplicate_invoice_`, `unusual_amount_`,
  `invoice_payment_mismatch_`, `fan_in_`, `fan_out_`, `pass_through_temporal_`,
  `circular_flow_dedup_`, `efos_negative_no_accusation_`

Agent evaluation packs live under `data/eval_corpus/` (also offline-only).

**What does not go here:** anything imported by `agent/`, `detection/`,
`backend/`, or `frontend/` at runtime.
