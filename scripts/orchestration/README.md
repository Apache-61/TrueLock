# scripts/orchestration/

**Purpose:** the executable implementation of the claim/verify protocol in
`tasks/README.md` and `history/decisions/ADR-0003-task-coordination.md`.

## `task_cli.py`

Stdlib-only (Python 3, no pip install needed). Requires `GITHUB_TOKEN`,
`GITHUB_OWNER`, `GITHUB_REPO`, `WORKER_ID` in the environment (see
`.env.example`).

```bash
python scripts/orchestration/task_cli.py list
python scripts/orchestration/task_cli.py claim --issue 42 --task-id TASK-004
python scripts/orchestration/task_cli.py verify --issue 42 --claim-id <uuid>
python scripts/orchestration/task_cli.py release --issue 42
```

`claim` posts a `CLAIM` comment (task_id/worker_id/claim_id/timestamp) and
adds the `status:claimed` label. `verify` re-fetches the issue's comments
and checks whether your `claim_id` is on the **earliest** `CLAIM` comment
by GitHub's own comment ID (server-assigned, effectively monotonic) — if
not, you lost the race and must abandon the task. `release` gives up a
task you claimed but aren't finishing (lost a race, got blocked, etc.).

The comment-ordering logic (`find_earliest_claim`) is a pure function
specifically so it can be unit-tested without hitting the GitHub API —
see `tests/unit/test_task_cli.py`.

**Known limitation:** this session had no `GITHUB_TOKEN` available to run
the CLI against the live API (the GitHub MCP tools available to this
session don't expose a way to mint one), so `claim`/`verify`/`release`
are verified by unit test against the pure comment-ordering logic only,
not by an end-to-end run against a real issue. Live-test this before
relying on it for the actual hackathon — see
`history/experiments/README.md` → "Orchestrator" row.

## Not yet built

Worker adapters that automatically *implement* a claimed task (Claude/
Gemini CLI invocations) — see
`tasks/ready/TASK-007-orchestrator-worker-adapters.md`. This bootstrap
only builds the coordination primitive (claim/verify), not automated
execution.
