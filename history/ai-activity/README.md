# AI activity log

**Purpose:** one entry per AI-worker task execution — the AI-to-AI handoff
record described in the operating pack (§16, §35), kept as durable history
rather than only living in a closed PR.

**What goes here:** `YYYY-MM-DD-task-###-slug.md` (or, for work not tied to
a single task, a descriptive slug) containing the same fields as a
`task-result.json` handoff: task, worker, branch, goal, changes made,
tests run/result, blocking reason (if any), PR link, next recommended
task, and any known limitations the next worker should know about.

**What does not go here:** raw chain-of-thought or full conversation
transcripts — only the structured, actionable summary.

**Depends on:** `orchestrator/` (handoff schema), `tasks/` (task IDs).

---

See `2026-09-12-bootstrap.md` for the first entry (this repository's
infrastructure bootstrap).
