# orchestrator/routing/

**Purpose:** which provider/project/model handles a call, and the
per-call spend record — implementing the routing rules documented in
`orchestrator/policies/provider-pool.yaml` with legitimate failover
(never quota circumvention; see `research/ai/README.md`).

**Status:** built, single-provider. `router.py` selects a provider and
logs every decision; `ledger.py` writes one row per call against
`orchestrator/policies/usage-ledger.schema.json`.

## The rule

> Every switch must be logged as `ROUTING_EVENT { from, to, reason }` so
> spend stays auditable. Never switch silently.

The implementation goes slightly further: *every selection* is logged,
not only switches, so the log answers "who served this task?" on its own
without replaying earlier events.

```
ROUTING_EVENT from=none to=claude-code-cli reason=TASK-001:feature:tier1-2-development
```

## Scope of this MVP

One provider is registered — the Claude Code CLI, which authenticates per
workstation rather than from the pooled Gemini keys. The pool file's four
Gemini projects are parsed and available to `select()`, but no Gemini
adapter exists yet: the end-to-end loop had to work first
(`tasks/ready/TASK-007-orchestrator-worker-adapters.md`).

Adding one means writing the adapter and calling
`router.select("gemini-project-a", reason=...)`. The routing, budget and
ledger machinery does not change.

## Costs

Recorded as the provider reports them, and left `null` when it reports
nothing. The worker never estimates a cost: an invented number in a
budget ledger is worse than an honest gap.

The pool file is read with PyYAML when it is installed and with a small
targeted reader when it is not — the worker must start on a fresh machine
without waiting on a dependency decision (`CONTRIBUTING.md` §5).
`tests/unit/test_worker_routing.py` asserts both readers agree on the
real file.

**Depends on:** `orchestrator/policies/provider-pool.yaml`,
`orchestrator/policies/usage-ledger.schema.json`.
