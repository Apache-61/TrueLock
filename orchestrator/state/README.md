# orchestrator/state/

**Purpose:** documents the shape of local runtime state, if/when a worker
adapter needs to persist something between runs (e.g. `.state/usage.json`
accumulating spend before it's rolled up).

**Never a source of truth** — GitHub Issues own task state
(`history/decisions/ADR-0003-task-coordination.md`); this is scratch
space. Gitignored except this README (`.gitignore`).

**What would go here:** `.state/tasks.json`, `.state/workers.json`,
`.state/usage.json`, `.state/locks.json`, `.state/events.jsonl` — per the
operating pack's shared-state model. None of these are implemented yet;
build them only when a worker adapter (`orchestrator/workers/`) actually
needs local caching, not preemptively.

**Never store secrets here.**
