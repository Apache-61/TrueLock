# ADR-0003: Task coordination source of truth for 4 parallel workers

**Status:** Accepted
**Date:** 2026-09-12
**Deciders:** bootstrap pass, per Research & Development Operating Pack
§9, §17-18

## Context

Four machines, several AI workers, will pick up tasks concurrently. A local
JSON file per machine cannot prevent two workers from claiming the same
task — they can both read `status: READY` at the same instant. We need a
central, network-visible source of truth for claims, without standing up a
new coordination service under time pressure.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Local `.state/tasks.json` per machine, synced via git | Simple | Not atomic across machines; merge conflicts *are* the race condition |
| Custom coordination server (Redis/DB) | Proper locking | New infrastructure to deploy/secure in a 31-hour build |
| **GitHub Issues as the lock** | Already used for task lifecycle/PRs/review; API is network-visible from all 4 machines; comments are ordered and timestamped | Not a true distributed lock (see mitigation below) |

## Decision

Use GitHub Issues as the central source of truth for task claims. Protocol
(full detail in `tasks/README.md`):

1. **CLAIM** — worker posts a comment on the task's issue containing a
   unique `claim_id` (UUID), its `WORKER_ID`, and a timestamp, then adds
   `status:claimed`.
2. **VERIFY** — the worker re-fetches the issue's comments and confirms its
   own claim comment is the earliest `CLAIM` comment by comment ID/creation
   time. If not, it lost the race: remove its own claim, do not touch
   `status:claimed`, and go find another task.

This is not a perfect distributed lock (GitHub could theoretically deliver
two comments with the same rendered timestamp), but combined with small
team size (4 workers) and the near-certainty that comment IDs are
monotonically assigned server-side, the residual race window is
acceptable for a hackathon and is cheap to detect after the fact (two
claim comments on the same issue is immediately visible).

## Consequences

No new infrastructure. Claim history is visible to humans without tooling
(just read the issue thread). The claim script
(`scripts/orchestration/task_cli.py`) is the only code that needs to
implement this; every worker (human or AI) uses the same script rather
than reimplementing the protocol.

## Reversibility

High — this is an operational script, not a structural dependency. If
GitHub API rate limits or availability become a problem mid-hackathon, the
fallback is manual claim-by-comment (same protocol, no script).
