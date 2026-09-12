# Status (at a glance)

> One-screen pulse check. For the structured, detailed snapshot (implemented
> / blocked / decisions / next tasks) see `PROJECT_STATE.md` — that file is
> the source of truth; this one is a quick pointer to it plus whatever is
> happening *right now*.

**Phase:** Repository reconciled, queue loaded. Still no product code;
the coordination layer is now fully live and four machines can run
unattended against a real backlog.

**Demo readiness:** 🔴 Not demoable — no detector/agent/UI exists yet.

**What just happened:** The bootstrap and the worker are merged to `main`
(PRs #8, #9) — the worker existed only on a branch with no PR, which is
why no workstation could run it. The real backlog is seeded: **55 tasks**
with a validated dependency graph, as GitHub issues and `tasks/BACKLOG.md`.
The worker now runs continuously (ADR-0006): it propagates merges so
dependent tasks unlock, works past blockers, polls when idle, and recovers
a crashed worker's claim. Repository labels exist at last.

**What's next:** Product code. Four tasks are claimable right now, one per
machine, with no overlapping scope:

| Machine | Task | What |
|---|---|---|
| 1 | `TASK-001` | Canonical entities & ingestion |
| 2 | `TASK-006` | Frontend shell against the mock |
| 3 | `TASK-052` | One-command local stack |
| 4 | `TASK-053` | Environment preflight |

```bash
worker status                              # eligibility, and why not
worker start --continuous --max-runtime 480
```

**The schedule risk:** the critical path to the end-to-end demo is seven
sequential merges — `TASK-001 → 002 → 009 → 005 → 025 → 026 → 049`.
Nothing parallelises it. **Review latency on those seven PRs is the
project's critical path**, not how fast the workers produce them.

**Known blockers:**
- Official challenge PDF not yet available — see `docs/challenge/README.md`.
- Branch protection still needs a human with `gh` repo-admin access to run
  `scripts/setup/branch_protection.sh` once.

**Budget:** ~USD 300 across 4 Gemini projects/accounts, ~$75 each. Ledger
format: `orchestrator/policies/provider-pool.yaml`. Nothing spent yet.
