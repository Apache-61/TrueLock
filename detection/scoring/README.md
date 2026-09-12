# detection/scoring/

**Purpose:** aggregate `DetectorSignal`s per entity into a documented,
deterministic `risk_score`, and produce a `Lead` when it crosses a
threshold. See `docs/contracts/leads.md` and `docs/detection/rules.md`
§Scoring.

**What goes here:** the weighting/threshold logic, and its documentation
(update this README with the actual weights once `TASK-004` sets them —
they must be citable when a judge asks "why this threshold").

**What does not go here:** the detectors themselves (→ `detection/rules/`),
any LLM-based scoring (scoring is deterministic — `ARCHITECTURE.md` §2).

**Depends on:** `detection/rules/`, `domain/schemas/lead.schema.json`.
