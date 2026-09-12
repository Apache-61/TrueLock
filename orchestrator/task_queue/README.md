# orchestrator/task_queue/

**Purpose:** placeholder for a local, human-readable mirror of task state,
if one proves useful beyond `tasks/{ready,active,...}/` + GitHub Issues.

**Right now:** GitHub Issues are the single source of truth for task
state (`history/decisions/ADR-0003-task-coordination.md`); `tasks/` is
the Markdown mirror. Nothing here yet — do not build a competing state
store unless the Markdown-file mirror genuinely proves insufficient.

**Depends on:** `tasks/README.md`.
