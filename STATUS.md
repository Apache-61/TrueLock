# Status (at a glance)

> One-screen pulse check. For the structured, detailed snapshot (implemented
> / blocked / decisions / next tasks) see `PROJECT_STATE.md` — that file is
> the source of truth; this one is a quick pointer to it plus whatever is
> happening *right now*.

**Phase:** Repository bootstrap (infrastructure for parallel AI/human
development). No product code yet.

**Demo readiness:** 🔴 Not demoable — no detector/agent/UI exists yet.

**What just happened:** Initial repository scaffold committed — contracts,
task queue, governance docs, claim-protocol script, CI baseline. See
`history/timeline.md` for the log and `history/ai-activity/` for the
bootstrap handoff record.

**What's next:** Pick up a task from `tasks/ready/` (mirrored as GitHub
issues). Priority order and dependencies are in `PROJECT_STATE.md` → "Next
authorized tasks."

**Known blockers:**
- Official challenge PDF not yet available — see `docs/challenge/README.md`.
- Label creation and branch-protection setup need a human with `gh`
  repo-admin access to run `scripts/setup/create_labels.sh` and
  `scripts/setup/branch_protection.sh` once (see `PROJECT_STATE.md` →
  "Blocked").

**Budget:** ~USD 300 across 4 Gemini projects/accounts, ~$75 each. Ledger
format: `orchestrator/policies/provider-pool.yaml`. Nothing spent yet.
