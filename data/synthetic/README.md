# data/synthetic/

**Purpose:** generated fraud scenarios — AMLSim-style patterns plus
hand-built SAT/CFDI-grounded rings — used for regression testing and the
demo (`docs/demo/runbook.md`).

**What goes here:** `scenario-*.json` (or per-scenario directories)
containing full canonical datasets (`domain/schemas/`) with a known,
injected fraud pattern.

**What does not go here:** the expected answers (→ `data/answer_keys/`,
kept separate on purpose), real/sensitive data.

**Depends on:** `domain/schemas/`, `research/fraud/README.md`.

Populated by `tasks/ready/TASK-003-synthetic-scenario-generator.md`.
