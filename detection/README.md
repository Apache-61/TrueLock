# detection/

**Purpose:** deterministic fraud-pattern detection over canonical data —
the first stage of the pipeline in `ARCHITECTURE.md` §1. Nothing in this
directory ever calls an LLM or a network service; see
`docs/contracts/detector.md` for the hard interface constraint.

**What goes here:** `rules/` (one file per detector from
`docs/detection/rules.md`), `scoring/` (aggregates signals into `Lead`s),
`graph/` (NetworkX-based traversal/cycle/fan-in-out analysis feeding both
detectors and, later, agent tools).

**What does not go here:** agent reasoning (`agent/`), API routes
(`backend/api/`), anything non-deterministic.

**Depends on:** `domain/entities/`, `domain/schemas/detector_signal.schema.json`,
`domain/schemas/lead.schema.json`, `docs/detection/rules.md`,
`docs/contracts/detector.md`.

**Owner:** Agent C (Detection/Graph). Must not touch: `frontend/**`,
`agent/**` (`CONTRIBUTING.md` §4).

Empty at bootstrap time — see `tasks/ready/TASK-004-detector-framework.md`.
