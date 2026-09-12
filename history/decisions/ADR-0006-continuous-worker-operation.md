# ADR-0006: Continuous worker operation across four machines

**Status:** Accepted
**Date:** 2026-09-12
**Deciders:** repository owner (directed the worker be turned into "a
continuous production loop that allows four computers to work
simultaneously without duplicating work"), implemented by an AI worker
session

## Context

ADR-0005 settled *how far* a worker may go on one task: autonomously up
to the pull request, never past it. It did not settle how a worker
behaves across *many* tasks, over hours, on four machines at once. The
worker as merged did one task well and then stopped, for any of several
reasons.

Seeding the real backlog (55 tasks, critical path 7 merges deep) made
three gaps load-bearing rather than theoretical:

1. **Nothing closed a task's issue when its PR merged.**
   `dependencies.check_eligibility` counts a dependency as satisfied only
   when its issue is closed or labelled `status:done`. A human merging
   TASK-001 therefore unlocked nothing. Four machines would have finished
   the first wave of claimable work and then reported "no eligible task"
   indefinitely — while the work they were waiting for was already in
   `main`.

2. **Any blocker ended the run.** A BLOCKED or PROPOSAL outcome stopped
   the whole worker. Both are *correct, expected* outcomes that leave a
   full explanation on the issue. Idling a machine until a human returns
   costs a quarter of the team's throughput for something that will be
   read later anyway.

3. **A claim never expired.** A worker killed mid-task — closed laptop,
   lost network, OOM — held its task forever. On the critical path that
   strands every task behind it, and the only remedy was a human noticing.

An empty queue also exited rather than waiting, which on this graph is
the common case: most tasks become claimable only when somebody else
merges something.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Leave it at `--once`, have humans re-run it | No new autonomy | A human babysits four machines for 23 hours; this is the coordination overhead the task system exists to remove |
| Let the worker merge its own PRs so dependants unlock | Fully unattended | Reverses ADR-0005. No human reads a diff before `main`, and `main` must stay demoable |
| **Propagate merges, keep working through blockers, poll when idle, expire silent claims** | Unattended for hours; humans stay the merge authority | More ways to run unattended means more ways to run unattended *wrongly*; needs explicit bounds |

## Decision

Add a continuous mode (`worker start --continuous`) that keeps the
ADR-0005 boundary exactly where it is and changes only what happens
*between* tasks:

* **Propagate, never decide.** Each pass reads whether a human merged the
  PR and records that outcome: label `status:done`, close the issue,
  which unlocks dependants. A PR closed unmerged releases the claim and
  returns the task to the queue. The worker still never merges and never
  judges work acceptable — it writes down a decision a human already made.
* **BLOCKED and PROPOSAL no longer end a continuous run.** The issue
  carries the explanation; the machine moves to the next eligible task.
  `--once` keeps the original stop-on-blocker behaviour, and
  `--stop-on-blocker` restores it for a continuous run.
* **An idle worker polls instead of exiting**, with jitter, so four
  machines that started from the same runbook do not wake in lockstep and
  race for the same task.
* **A claim expires after `WORKER_CLAIM_STALE_MINUTES` of silence on its
  issue** (default 180, three times the longest a single task may run).
  Expiry is recorded as a RELEASE — the protocol's own primitive — so a
  human running `task_cli.py` sees the same thing the worker does, and
  nothing in `find_winning_claim` needs a special case.

Bounds, because a loop that can run forever on an unattended machine
will: `--max-tasks`, `--max-runtime`, `--max-idle`, and a failure circuit
breaker that stops after three consecutive failed tasks. Unrelated tasks
failing in a row is evidence the machine is misconfigured, not that the
tasks are bad, and continuing burns budget and fills the queue with
failure comments.

## Consequences

**Good.** Four machines can run `worker start --continuous` and keep
working through a 55-task graph without a human dispatching them.
Dependants unlock within one poll of a merge. A crashed worker's task
returns to the queue on its own.

**Accepted cost.** Claim expiry weakens the mutual-exclusion guarantee
from "impossible" to "impossible unless a worker is silent for three
hours and then resumes". The threshold is deliberately generous and the
takeover is loud: it posts a RELEASE naming both workers and telling a
human to stop the other one if it is still alive. The alternative — a
task stranded until someone notices — was the worse failure.

**Unchanged.** Merge authority. The worker opens pull requests and a
human merges them (ADR-0005, `CONTRIBUTING.md` §5). Everything added here
runs strictly before that line or strictly after a human has crossed it.
