# orchestrator/

**Purpose:** the AI-to-AI coordination layer — how four workers (human or
AI) avoid duplicating work, hand off between each other without copying
full conversation transcripts, and stay within budget. See
`research/ai/README.md` for the cost side and
`history/decisions/ADR-0003-task-coordination.md` for why GitHub Issues
are the source of truth rather than a bespoke server.

**What goes here:** `task_queue/` (mirrors GitHub Issues for readability),
`workers/` (the AI development worker — adapters that invoke Claude to
implement a claimed task, and the loop around them), `routing/` (which
provider/model handles a task, per the tier system below), `policies/`
(provider pool, budgets, model-tier rules, handoff schema), `state/`
(local runtime state — gitignored, never a source of truth, see
`.gitignore`).

**What does not go here:** the forensic agent (`agent/`) — this
orchestrator builds the repository; the forensic agent investigates
financial data. Never mix the two prompts/authorities
(`ARCHITECTURE.md` §6/§57).

## Running the worker

```bash
export WORKER_ID="WORKER-01"
export PATH="$PWD/scripts/orchestration:$PATH"

worker doctor                  # check this machine's setup
worker start --once --dry-run  # rehearse: changes nothing, calls no paid API
worker start --once            # claim and execute one task
worker start --continuous --max-tasks 5 --max-runtime 90
```

Full installation, authentication, commands and troubleshooting:
[`docs/orchestration/worker-setup.md`](../docs/orchestration/worker-setup.md).

Safety limits: `--once` (the default), `--continuous`, `--max-tasks N`,
`--max-runtime MINUTES`, `--dry-run`. A continuous run stops when no
eligible READY task remains, a task ends BLOCKED, a task needs human
authorization, a critical error occurs, or a limit is reached.

The worker **never merges**. Every run ends at an open pull request and a
human decides (`CONTRIBUTING.md` §5). See
`orchestrator/workers/merge_policy.py` for the three independent
conditions `--allow-auto-merge` requires before it would merge even a
pre-authorized simple task.

## AI task execution protocol

Every worker (human or AI) follows this sequence for a task. Steps 1-12
are what `worker start` automates; a human doing it by hand follows the
same list.

```
1. READ REPO             (PROJECT_STATE.md, relevant docs/contracts/)
2. READ STATUS           (STATUS.md, PROJECT_STATE.md → "In progress")
3. READ TASK             (tasks/ready/TASK-XXX-*.md)
4. CHECK AUTHORIZATION   (CONTRIBUTING.md §5 - does this need human sign-off?)
5. CHECK DEPENDENCIES    (task's depends_on, all must be MERGED/VERIFIED)
6. CREATE/USE BRANCH     (CONTRIBUTING.md §3 naming convention)
7. IMPLEMENT
8. RUN TESTS
9. RUN CONTRACT CHECKS   (tests/contract/, scripts/validate/)
10. WRITE HANDOFF         (see below)
11. CREATE PR
12. STOP
```

A worker does **not** automatically start the next unrelated task unless
the task explicitly says autonomous chaining is allowed.

## AI-to-AI handoff format

Every completed (or blocked) task produces this, either as a
`task-result.json` file attached to the PR/issue or as the PR
description body:

The schema is `orchestrator/policies/task-result.schema.json`, validated
against real worker output in `tests/contract/`.

```json
{
  "task_id": "DET-004",
  "status": "DONE",
  "summary": "Detector framework exists, but canonical payment schema is missing.",
  "changed_files": ["detection/rules/duplicate_invoice.py"],
  "tests": { "passed": 14, "failed": 0 },
  "new_dependencies": [],
  "known_issues": [],
  "next_recommended_tasks": ["TASK-005"],
  "requires_human_review": false
}
```

The next worker reads this plus the repository state — never a full
conversation transcript. This is what `history/ai-activity/` stores
long-term.

## Model/worker routing tiers

Don't use the strongest model for every task — see
`research/ai/README.md` §Model-tier routing for the TIER 0-3
classification, which applies to development workers too, not just the
forensic agent.

## Budget

`policies/provider-pool.yaml` holds the 4 Gemini project/key pool
(~$75 each, ~$300 total) and the routing/failover rules. A
`ROUTING_EVENT` is logged (`from`, `to`, `reason`) every time the router
switches providers, so spend stays auditable
(`history/decisions/ADR-0003-task-coordination.md` sibling reasoning
applies here too: never silently switch).

## What's implemented vs. not, right now

**Implemented:**

- the claim/verify protocol, twice over: manually via
  `scripts/orchestration/task_cli.py`, and inside the worker
  (`orchestrator/workers/claim.py`). Both emit and parse the same wire
  format, so a human and a worker contend correctly against each other —
  asserted by `tests/unit/test_worker_claim.py`;
- the AI development worker (`orchestrator/workers/`): claim, dependency
  and scope gates, isolated branch, bounded context pack, Claude Code
  execution, validation pipeline, handoff, history entry, and PR;
- provider routing with `ROUTING_EVENT` logging and the per-call usage
  ledger (`orchestrator/routing/`);
- the provider-pool policy, the usage-ledger schema, and the handoff
  schema (`orchestrator/policies/`).

**Not implemented, deliberately:**

- **Gemini and multi-provider routing.** One provider (the Claude Code
  CLI) is wired up. The routing layer is real, so adding Gemini is a
  registration rather than a rewrite — but the end-to-end loop had to
  work first.
- **Waiting for CI.** The worker opens the PR and stops; it does not poll
  for the result.
- **Auto-merge in practice.** The policy gate exists and is tested, but
  the default — and the only behaviour anyone should rely on — is that a
  human merges.
