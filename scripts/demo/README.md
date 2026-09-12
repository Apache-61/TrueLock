# scripts/demo/

**Purpose:** the executable side of `docs/demo/runbook.md` — loading a
scenario, injecting a hidden fraud pattern for judges, resetting between
runs.

**What goes here:** `load_scenario.py`, `inject_fraud.py`, `reset_demo.py`
(names indicative — implement as needed). These back the
`POST /demo/inject-fraud` endpoint (`docs/contracts/api.md`) and/or run
standalone for a CLI-driven demo.

**Depends on:** `data/synthetic/`, `data/answer_keys/` (read only by the
team afterward, never by the running system — see
`data/answer_keys/README.md`).
