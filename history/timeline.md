# Timeline

Append-only. One line per completed task or notable event, newest at the
bottom. This is the fast-scan version of history; full detail lives in
`history/changes/`, `history/decisions/`, and `history/ai-activity/`.

Format: `YYYY-MM-DD HH:MM UTC | TASK-### or n/a | worker | one-line summary`

---

2026-09-12 00:00 UTC | n/a | bootstrap (Sonnet 5, session) | Repository infrastructure bootstrap: governance docs, full module scaffold, domain contracts, task queue + claim protocol, GitHub governance files, CI baseline. See `history/ai-activity/2026-09-12-bootstrap.md`.

2026-09-12 09:40 UTC | TASK-007 | Claude Code session (human-directed) | AI development worker MVP: `worker start` takes a task from the GitHub queue to an open PR (claim/verify, dependency + scope gates, bounded context, Claude Code execution, validation, handoff, history, PR). Never touches `main`, never merges. 334 tests passing. See `history/ai-activity/2026-09-12-task-007-ai-development-worker.md` and ADR-0005.

2026-09-12 11:15 UTC | TASK-007 | Claude Code session (human-directed) | Worker verified against the real Claude Code CLI (opt-in test `tests/integration/test_worker_live_claude.py`). Five defects found and fixed: PARTIAL promoted to DONE, `requires_human_review` ignored for PR readiness, `is_error` envelope unchecked, permission denials invisible, and worker scratch committed into the branch. 352 tests passing.

2026-09-12 16:20 UTC | n/a | orchestrator session (Claude Code) | Repository reconciled: bootstrap (PR #8) and the worker/control plane (PR #9) merged to `main`. The worker existed only as a branch with no PR, which is why no workstation could run it. Both source branches preserved, no history rewritten.

2026-09-12 16:45 UTC | n/a | orchestrator session (Claude Code) | Real task queue seeded: 55 tasks with a validated dependency graph (`orchestrator/task_queue/backlog.py` -> `tasks/BACKLOG.md` + GitHub issues #1-#57). 48 issues created, 6 updated in place, TASK-007 closed as merged. All 31 repository labels created, clearing a documented blocker.

2026-09-12 17:30 UTC | n/a | orchestrator session (Claude Code) | Continuous worker loop (ADR-0006): merges propagate into task state so dependants unlock, blockers no longer idle a machine, idle workers poll with jitter, and silent claims expire. Bounded by `--max-idle` and a three-failure circuit breaker. 446 tests passing.

2026-09-12 19:10 UTC | TASK-001 | orchestrator session (Claude Code) | Canonical domain layer: six entities mirroring `domain/schemas/` with reject-don't-guess validation, CFDI/bank-CSV ingestion reporting every rejection, and the repository read surface as Protocols with no database dependency (plus in-memory implementations). 577 tests passing. Fixed two backlog defects found by doing the work: no task declared `tests/` in its allowed_paths (the scope guard would have blocked every task from writing its required tests), and `task_cli.py` sent no Content-Type so every manual claim failed with 415.

