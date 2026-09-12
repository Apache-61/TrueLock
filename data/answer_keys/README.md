# data/answer_keys/

**Purpose:** the expected output (leads, path, evidence, amount,
conclusion, discarded leads — `docs/testing.md`) for each
`data/synthetic/` scenario. This is ground truth used **only** by test
code and the team, after a demo run, to score the agent — never read by
`agent/`, `detection/`, `backend/`, or `frontend/` at runtime.

**What goes here:** `scenario-*.json` matching each synthetic scenario's
ID, in the shape described in `docs/testing.md` §Scenario regression.

**What does not go here:** anything the running system reads. If a module
under `agent/`, `backend/`, or `frontend/` ever imports from this
directory, that's a bug — it defeats the point of a hidden-fraud demo.

**Depends on:** `data/synthetic/`.
