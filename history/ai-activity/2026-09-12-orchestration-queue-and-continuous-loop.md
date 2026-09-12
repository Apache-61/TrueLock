# 2026-09-12 — Repository reconciliation, real task queue, continuous worker loop

- **task_id:** n/a — orchestration session commissioned directly by the
  repository owner, not an autonomous `worker start` run
- **worker:** Claude Code session (`session_01HCuj7J8sDnxffXHCVsnZeV`),
  human-directed
- **branch:** `claude/peaceful-noether-5lzmqd` (based on `main` after
  reconciliation)
- **start:** 2026-09-12
- **end:** 2026-09-12
- **result:** DONE — 446 tests passing; queue seeded and live

## Goal

Three things, in order: reconcile the repository so `main` carries the
work that existed only on branches; seed the real implementation backlog;
turn the worker into a continuous loop four machines can run
simultaneously without duplicating work.

## 1. Reconciliation

The repository state was:

```
main (3b75e65)  "Initial commit" — a 10-byte README, nothing else
  └── 24faab5   bootstrap        (branch vigilant-noether-yzghll, PR #8 open)
        └── 73275fc + 8265f0e    worker (branch vigilant-hamilton-6u3jg6, NO PR)
```

Strictly linear — the worker branch already contained the bootstrap, so
there was no overlap to resolve and nothing to lose. The finding that
mattered: **the worker branch had no pull request at all.** That is why
the 352-test, fully-tested worker had never reached `main`, and why no
workstation could run it. PR #8 was open; nobody had opened one for the
worker.

Merged PR #8, opened and merged PR #9 for the worker. `main` now carries
all 187 files. Both source branches are preserved, nothing was
force-pushed, no history was rewritten.

## 2. The real task queue

The queue held 7 bootstrap tasks against a product core spanning data →
normalization → detection → leads → investigation tools → AI investigator
→ evidence → case → frontend → Q&A. Four machines had almost nothing
eligible.

`orchestrator/task_queue/backlog.py` now defines 55 tasks as data, and
`scripts/orchestration/seed_backlog.py` renders them into both the
`tasks/` mirror and the GitHub issues — one source, so the mirror cannot
drift from the queue.

Two guards, because both failures are invisible when they happen:

- **Deadlock.** A cycle makes every worker report "no eligible task" with
  no explanation, on all four machines at once. Indistinguishable from an
  empty queue.
- **Collision.** Two tasks with no dependency between them declaring
  overlapping `allowed_paths` can be claimed simultaneously. The claim
  protocol stops two workers taking one *task*; it does nothing about two
  tasks touching one *file*. Enforcing this is what drove the per-file
  scoping of the detectors, the API endpoints and the frontend screens.

Three dependencies in the original spine were false, and correcting them
shortened the critical path to the end-to-end demo from 9 sequential
merges to 7: the tool layer needs the repositories, not the detectors
that populate them; evidence accumulation needs the `ToolResult`
contract, not the loop that drives it; `GET /cases/{id}` needs the `Case`
type, not the generator. Each is built against fixtures exactly as the
frontend shell is built against its mock.

Seeded: 48 issues created, 6 updated in place, TASK-007 closed as merged.

## 3. The continuous loop (ADR-0006)

Seeding a 7-deep graph turned three latent gaps into blocking ones:

**Nothing closed a task's issue when its PR merged.** Eligibility counts
a dependency as satisfied only when its issue is closed or labelled
`status:done`. A human merging TASK-001 unlocked *nothing*. Four machines
would have finished the first wave and then idled indefinitely — while
the work they were waiting for was already in `main`. `completion.py`
propagates the merge: label, close, dependants unlock. A PR closed
unmerged releases the claim instead.

**Any blocker ended the run.** BLOCKED and PROPOSAL are correct, expected
outcomes that leave a full explanation on the issue. Stopping a machine
for one costs a quarter of the team's throughput. A continuous run now
moves to the next task; `--once` and `--stop-on-blocker` keep the old
behaviour.

**A claim never expired.** A worker killed mid-task held its task
forever. Claims now expire after three hours of silence on the issue,
recorded as a `RELEASE` — the protocol's own primitive, so `task_cli.py`
and `find_winning_claim` need no special case.

Plus: idle workers poll with jitter rather than exiting, so four machines
started from the same runbook do not wake in lockstep and race for the
same task.

Bounds, because a loop that can run unattended forever will: `--max-tasks`,
`--max-runtime`, `--max-idle`, and a three-consecutive-failure circuit
breaker — unrelated tasks failing in a row is evidence the machine is
misconfigured, not that the tasks are bad.

**Merge authority is unchanged.** The worker still never merges and never
judges work acceptable. Everything added runs strictly before the PR or
strictly after a human has merged it.

## Also fixed

- **Repository labels now exist** (all 31). `PROJECT_STATE.md` recorded
  this as blocked on a human with `gh` repo-admin access; the REST API
  accepts label creation with an ordinary repo-scoped token, which this
  session had. The worker's label-less fallback is no longer the only path.
- **`list_issues` now paginates.** GitHub caps a page at 100 items and
  counts pull requests against that cap, so a single-page read silently
  drops tasks past ~100 issues — which a worker reports as "no eligible
  task". The queue is already at 57.
- **`create_issue`/`update_issue`** on the existing client, so the seeder
  updates a task's issue in place rather than opening a second one. A
  duplicate splits the task's claim history, and the claim protocol only
  holds while there is exactly one comment thread per task.

## Tests

446 passing (from 352). New: `tests/unit/test_backlog.py` (26) asserts
the graph guards and that what the seeder renders is what the worker
parses; `tests/unit/test_worker_continuous.py` (20) covers merge
propagation and the actual unlock, working past blockers, idle polling
and jitter, the failure circuit breaker, and claim expiry — including
that a *live* claim still blocks another worker, which is the property
staleness must not weaken.

## Known issues / for the next worker

- **The seven-merge critical path is the schedule risk.**
  `TASK-001 → 002 → 009 → 005 → 025 → 026 → 049`. Nothing parallelises
  it. Review latency on those PRs, not worker throughput, decides whether
  the demo exists.
- **Claim expiry weakens mutual exclusion** from "impossible" to
  "impossible unless a worker is silent for three hours and then
  resumes". Deliberate trade (ADR-0006); the takeover is loud and names
  both workers.
- **Branch protection is still unset.** `main` has no required review or
  status check. Needs a human with `gh` repo-admin access to run
  `scripts/setup/branch_protection.sh` once.
- **TASK-005 and TASK-006 are coarser than the rest** — "the tool layer"
  and "the frontend shell". Both were seeded during bootstrap and are
  deliberately left as spine tasks that establish a seam others plug
  into; their remainder is decomposed into TASK-028..031 and
  TASK-040..047. If either proves too big for one worker, split it rather
  than letting it run long.
- Issue #58 is a duplicate of #57, created by a seeder run against a
  stale issue list before the de-duplication guard existed. Closed as a
  duplicate; the guard now reports rather than guesses.
