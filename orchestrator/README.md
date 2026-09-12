# orchestrator/

**Purpose:** the AI-to-AI coordination layer — how four workers (human or
AI) avoid duplicating work, hand off between each other without copying
full conversation transcripts, and stay within budget. See
`research/ai/README.md` for the cost side and
`history/decisions/ADR-0003-task-coordination.md` for why GitHub Issues
are the source of truth rather than a bespoke server.

**What goes here:** `task_queue/` (mirrors GitHub Issues for readability),
`workers/` (adapters that invoke Claude/Gemini to implement a claimed
task — not yet built, see `tasks/ready/TASK-007-orchestrator-worker-adapters.md`),
`routing/` (which provider/model handles a task, per the tier system
below), `policies/` (provider pool, budgets, model-tier rules), `state/`
(local runtime state — gitignored, never a source of truth, see
`.gitignore`).

**What does not go here:** the forensic agent (`agent/`) — this
orchestrator builds the repository; the forensic agent investigates
financial data. Never mix the two prompts/authorities
(`ARCHITECTURE.md` §6/§57).

## AI task execution protocol

Every worker (human or AI) follows this sequence for a task:

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

Implemented: the claim/verify protocol
(`scripts/orchestration/task_cli.py`), the provider-pool policy file, the
usage-ledger schema. Not implemented: automated worker adapters that
actually invoke Claude/Gemini to write code
(`tasks/ready/TASK-007-orchestrator-worker-adapters.md`) — that requires
human authorization per `CONTRIBUTING.md` §5 (new infrastructure that
calls paid APIs autonomously).
