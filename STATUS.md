# Status (at a glance)

> One-screen pulse check. For the structured, detailed snapshot (implemented
> / blocked / decisions / next tasks) see `PROJECT_STATE.md` — that file is
> the source of truth; this one is a quick pointer to it plus whatever is
> happening *right now*.

**Phase:** Repository bootstrap + automation. Still no product code; the
coordination layer can now execute tasks instead of only describing them.

**Demo readiness:** 🔴 Not demoable — no detector/agent/UI exists yet.

**What just happened:** The AI development worker landed (TASK-007). A
workstation can run `worker start --once` and take a task from the GitHub
queue to an open pull request: claim → verify → branch → Claude → tests →
handoff → PR. It never touches `main` and never merges. Setup:
`docs/orchestration/worker-setup.md`. See `history/timeline.md` for the
log and `history/ai-activity/` for the handoff records.

**What's next:** Execute the critical path. `TASK-001` (canonical
ingestion) and `TASK-006` (frontend shell) are the two startable P0 tasks
— everything else waits on them. Either pick one up by hand
(`tasks/ready/`, mirrored as GitHub issues) or point a worker at it:

```bash
worker status                  # what is eligible, and why the rest is not
worker start --once --dry-run  # rehearse
worker start --once
```

**Known blockers:**
- Official challenge PDF not yet available — see `docs/challenge/README.md`.
- Label creation and branch-protection setup need a human with `gh`
  repo-admin access to run `scripts/setup/create_labels.sh` and
  `scripts/setup/branch_protection.sh` once (see `PROJECT_STATE.md` →
  "Blocked"). The worker works without labels, but task state is then
  only readable from issue bodies and claim comments.

**Budget:** ~USD 300 across 4 Gemini projects/accounts, ~$75 each. Ledger
format: `orchestrator/policies/provider-pool.yaml`. Nothing spent yet.
