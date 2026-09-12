# orchestrator/workers/

**Purpose:** adapters that, given a claimed task, invoke a specific AI
(Claude Code CLI, Gemini API/CLI, or a local model) to implement it,
capture the result, and produce the handoff described in
`orchestrator/README.md`.

**Not yet built** — requires human authorization
(`CONTRIBUTING.md` §5) since it's new infrastructure that calls paid
APIs autonomously. See `tasks/ready/TASK-007-orchestrator-worker-adapters.md`.

**What would go here:** `claude.py`, `gemini.py`, `local.py` — one adapter
per worker type, each implementing the same interface (take a task
description, return a handoff).

**Depends on:** `scripts/orchestration/task_cli.py` (claim/verify),
`orchestrator/policies/provider-pool.yaml` (routing/budget).
