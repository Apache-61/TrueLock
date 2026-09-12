# orchestrator/workers/

**Purpose:** the AI development worker — adapters and the loop that,
given a claimed task, invoke an AI to implement it, validate the result,
and produce the handoff described in `orchestrator/README.md`.

**Status:** built. `worker start` runs
`TASK → CLAIM → BRANCH → CLAUDE → TEST → HISTORY → PR` end to end. See
`docs/orchestration/worker-setup.md` for installation and operation, and
`tasks/ready/TASK-007-orchestrator-worker-adapters.md` for the task this
implements.

```bash
export PATH="$PWD/scripts/orchestration:$PATH"
worker doctor              # check this machine
worker start --once --dry-run
worker start --once
```

## Module map

| Module | Responsibility |
|---|---|
| `cli.py` | `worker start` / `status` / `doctor` |
| `runner.py` | the loop: the 16 steps, in order |
| `config.py` | identity (`WORKER_ID`), tokens, `.env` |
| `github.py` | REST client, plus the dry-run and in-memory doubles |
| `tasks.py` | GitHub issue → `TaskSpec` (priority, deps, paths) |
| `claim.py` | CLAIM → VERIFY (`tasks/README.md`, ADR-0003) |
| `dependencies.py` | the eligibility gate |
| `scope.py` | `allowed_paths` / `forbidden_paths` enforcement |
| `gitops.py` | branches, commits, pushes — never `main` |
| `context.py` | the bounded context pack |
| `adapters/` | `claude_code.py`, `mock.py`, and the result contract |
| `validation.py` | formatter → lint → types → unit → integration |
| `handoff.py` | `task-result.json` + the `history/ai-activity/` entry |
| `pullrequest.py` | PR body, and the `execution:human` proposal |
| `merge_policy.py` | what may never be merged without a human |
| `safety.py` | run limits and destructive-command refusal |

## The rules this code exists to enforce

1. **Two workers never execute one task.** Claiming is posting *and*
   re-reading; the earliest live claim by GitHub comment ID wins. A
   worker that loses writes no code (`claim.py`).
2. **Nothing outside the task's paths changes.** An out-of-scope diff
   stops the task, marks it BLOCKED, and explains what is missing. The
   worker never widens its own scope (`scope.py`).
3. **A failing task never looks like a passing one.** A skipped gate is
   not a pass; an unverified change is a draft PR (`validation.py`).
4. **`main` is never touched, and nothing is ever merged**
   (`gitops.py`, `merge_policy.py`).
5. **`execution:human` means propose, not implement** (`runner.py`).

## Extending it

A new AI backend implements `adapters/base.AIAdapter`: one `execute()`
that takes a prompt and returns an `AIResult`. Register it in
`cli._make_adapter` and, if it draws on a pooled budget, add its provider
to `orchestrator/policies/provider-pool.yaml` so routing and the usage
ledger see it.

**Depends on:** `scripts/orchestration/task_cli.py` (the same claim wire
format), `orchestrator/policies/` (budget, ledger and handoff schemas),
`orchestrator/routing/` (provider selection).
