# Task system

The task queue for parallel development across 4 machines/AIs. GitHub
Issues are the source of truth for task **state and claims**
(`history/decisions/ADR-0003-task-coordination.md`); the files under
`tasks/{backlog,ready,active,blocked,completed}/` are a human-readable
mirror, one Markdown file per task, kept in sync by whoever moves a task
through the state machine. If the mirror and the GitHub issue ever
disagree, **the GitHub issue wins.**

## State machine

```
RESEARCH → PROPOSAL → WAITING_AUTHORIZATION → READY → CLAIMED →
IN_PROGRESS → TESTING → READY_FOR_REVIEW → MERGED → VERIFIED
```

Terminal states, reachable from anywhere: `BLOCKED`, `REJECTED`,
`CANCELLED`.

| State | Meaning | Mirror folder |
|---|---|---|
| RESEARCH | Still figuring out if/how to do this | `tasks/backlog/` |
| PROPOSAL | Scoped, written up, not yet authorized | `tasks/backlog/` |
| WAITING_AUTHORIZATION | Needs a human sign-off (`CONTRIBUTING.md` §5) | `tasks/backlog/` |
| READY | Authorized, no unmet dependencies, unclaimed | `tasks/ready/` |
| CLAIMED | A worker has claimed it (see protocol below) | `tasks/active/` |
| IN_PROGRESS | Worker is actively implementing | `tasks/active/` |
| TESTING | Implementation done, tests running | `tasks/active/` |
| READY_FOR_REVIEW | PR open, tests passing | `tasks/active/` |
| MERGED | PR merged into `main` | `tasks/completed/` |
| VERIFIED | A second party (human or different AI) confirmed it works | `tasks/completed/` |
| BLOCKED | Can't proceed — dependency, missing info, external outage | `tasks/blocked/` |
| REJECTED | Decided against — record why in `history/rejected-ideas/` | `tasks/completed/` (with rejection note) |
| CANCELLED | No longer needed | `tasks/completed/` (with cancellation note) |

Moving a task's Markdown file between folders **is** the state
transition for the mirror; the corresponding GitHub label
(`status:*`, see `docs/contracts` label list in
`.github/ISSUE_TEMPLATE/`) must be updated in the same action.

## Claim protocol — CLAIM then VERIFY

Two workers can both read `status:ready` at the same instant. Reading is
not claiming. Use `scripts/orchestration/task_cli.py` (or follow this
protocol by hand if the script is unavailable):

### 1. CLAIM

```bash
python scripts/orchestration/task_cli.py claim --issue <number> --worker-id "$WORKER_ID"
```

This posts a comment on the task's GitHub issue:

```
CLAIM
task_id: TASK-004
worker_id: WORKER-02
claim_id: 7c1e2b9e-...
timestamp: 2026-09-12T14:03:00Z
```

and adds the `status:claimed` label.

### 2. VERIFY

```bash
python scripts/orchestration/task_cli.py verify --issue <number> --claim-id <uuid>
```

This re-fetches the issue's comments and checks whether **your**
`claim_id` is on the earliest `CLAIM` comment (by GitHub comment ID/
creation time, which is server-assigned and monotonic).

- **You won the race:** proceed — move the task file to `tasks/active/`,
  set state to `CLAIMED`, create your branch.
- **You lost the race:** abandon immediately. Do not implement "just in
  case." Remove your claim comment or mark it superseded, and go claim a
  different `READY` task.

See `history/decisions/ADR-0003-task-coordination.md` for why GitHub
Issues (not a local file) are the source of truth, and the accepted
residual risk.

## Worker ID

Every machine sets a `WORKER_ID` once (`WORKER-01`..`WORKER-04`, or a
descriptive slug) — never rely on a shared GitHub username as identity.
See `CONTRIBUTING.md` §1 and `.env.example`.

## Branch policy

One branch per task, named from the task's type and ID:

```
feature/TASK-001-canonical-ingestion
research/TASK-013-langgraph-spike
fix/TASK-022-lead-threshold-bug
experiment/TASK-030-cytoscape-scale-test
```

Never commit to `main` directly. See `CONTRIBUTING.md` §3.

## Task template

Every task file (backlog, ready, or GitHub issue) has these fields — see
`tasks/templates/task-template.md`:

```
TASK ID, title, objective, type, priority (P0-P3), status, execution_mode
(auto | human), dependencies, allowed_paths, forbidden_paths, input,
output, acceptance_criteria, tests, documentation_requirements,
human_authorization (yes/no + who)
```

## Priority

`P0` (blocks multiple modules / on the critical path) → `P1` (needed
before demo but not blocking) → `P2` (improves the demo) → `P3` (nice to
have, cut first under time pressure).

## Handoff on completion

When a task reaches `READY_FOR_REVIEW` or later, write the handoff
described in `orchestrator/README.md` → "AI-to-AI handoff format" (or the
same fields in the PR description if done by hand), and add one line to
`history/timeline.md`.
