# frontend/

**Purpose:** the investigation UI — the screens listed in
`docs/demo/runbook.md` (dashboard, investigation view, graph, money
trail, evidence, case file, Q&A).

**What goes here:** the Next.js/TypeScript app, built against
`docs/contracts/api.md`. Until `backend/` is ready, build against a mock
implementation of that same contract (static fixtures) so both sides can
progress in parallel.

**What does not go here:** any business logic that decides what counts as
suspicious (that's `detection/`/`agent/`, exposed only through the API) —
the frontend renders what the API returns, it does not compute risk
scores or evidence itself.

**Depends on:** `docs/contracts/api.md`, `research/graph/README.md`
(Cytoscape.js).

**Owner:** Agent A (Frontend). Must not touch: `domain/**`,
`detection/**`, `database/**`, `agent/**` (`CONTRIBUTING.md` §4).

Empty at bootstrap time — see `tasks/ready/TASK-006-frontend-shell.md`.
