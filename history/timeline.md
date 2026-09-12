# Timeline

Append-only. One line per completed task or notable event, newest at the
bottom. This is the fast-scan version of history; full detail lives in
`history/changes/`, `history/decisions/`, and `history/ai-activity/`.

Format: `YYYY-MM-DD HH:MM UTC | TASK-### or n/a | worker | one-line summary`

---

2026-09-12 00:00 UTC | n/a | bootstrap (Sonnet 5, session) | Repository infrastructure bootstrap: governance docs, full module scaffold, domain contracts, task queue + claim protocol, GitHub governance files, CI baseline. See `history/ai-activity/2026-09-12-bootstrap.md`.

2026-09-12 09:40 UTC | TASK-007 | Claude Code session (human-directed) | AI development worker MVP: `worker start` takes a task from the GitHub queue to an open PR (claim/verify, dependency + scope gates, bounded context, Claude Code execution, validation, handoff, history, PR). Never touches `main`, never merges. 334 tests passing. See `history/ai-activity/2026-09-12-task-007-ai-development-worker.md` and ADR-0005.
