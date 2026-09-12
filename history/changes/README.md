# Changes log

**Purpose:** one file per merged task, capturing what changed and why, in
more detail than the one-liner in `history/timeline.md` but less formal
than a full ADR. Not every commit — one entry per completed task.

**What goes here:** `TASK-###-summary.md` files with: task, worker,
branch, goal, changed files, tests run/result, PR link, next recommended
work. This is the same content as the task's `task-result.json` handoff
(see `orchestrator/README.md`), kept human-readable.

**What does not go here:** architectural rationale (→ `history/decisions/`),
raw AI session transcripts, anything not tied to a specific completed task.

**Depends on:** `tasks/` (a change entry should reference its task ID).
