# orchestrator/state/

**Purpose:** documents the shape of local runtime state written by a
worker adapter between runs.

**Never a source of truth** — GitHub Issues own task state
(`history/decisions/ADR-0003-task-coordination.md`); this is scratch
space. Gitignored except this README (`.gitignore`).

**What the worker writes today**, under `.state/` at the repository root:

| File | Contents |
|---|---|
| `.state/usage.jsonl` | one usage-ledger row per AI call, append-only |
| `.state/task-result-<run-id>.json` | the handoff for one task execution |

Append-only JSON Lines for the ledger is deliberate: it survives a
crashed run, which a rewritten JSON document does not.

The durable copy of a handoff lives in `history/ai-activity/` and in the
PR body; these files are the local working copy. Deleting `.state/` at
any time is safe.

**Never store secrets here.**
