# Project State

> The detailed, structured snapshot of where TrueLock stands. Read this
> before doing anything else — it exists so a new contributor (human or AI)
> can get oriented without reading the whole conversation history. For a
> one-glance pulse check instead, see `STATUS.md`. Update this file as part
> of any task that changes what's implemented, blocked, or decided.

**Last updated:** 2026-09-12 · **Updated by:** orchestrator session
(repository reconciliation, real task queue, continuous worker loop)

## Current version

`v0.0.2-queue` — still no *product* code (no detector, agent, or UI).
What is new is that the automation layer is **on `main` and loaded**: the
bootstrap and the worker are merged, the real 55-task backlog is seeded as
GitHub issues, and the worker runs as a continuous loop four machines can
share. The next thing to land should be product code.

## Current architecture

See `ARCHITECTURE.md` for the full write-up. Summary: deterministic
detection + graph tracing, Gemini-driven investigation/narrative layer,
PostgreSQL persistence, NetworkX for graph analysis, Next.js/FastAPI for
frontend/backend, custom bounded agent loop (no LangGraph unless it becomes
necessary).

## Implemented

- Repository structure matching the module map in `docs/contracts/` and
  the Research & Development Operating Pack.
- Root governance docs: `ARCHITECTURE.md`, `CONTRIBUTING.md`,
  `SECURITY.md`, `DECISIONS.md`, `CHANGELOG.md`, this file.
- Domain contracts (JSON Schema + prose) for: canonical entities
  (provider/invoice/payment/account), lead, evidence, investigation step,
  case, detector signal. See `domain/schemas/` and `docs/contracts/`.
- Task system: state machine, claim/verify-claim protocol, task template,
  worker-ID convention. See `tasks/README.md`.
- GitHub scaffolding: PR template, issue templates, CODEOWNERS,
  `.github/workflows/ci.yml` baseline.
- Orchestrator claim-protocol script
  (`scripts/orchestration/task_cli.py`) using GitHub Issues as the
  source of truth for task claims.
- Baseline contract tests validating that every JSON Schema file is
  well-formed and internally consistent (`tests/contract/`).
- **AI development worker** (`orchestrator/workers/`, TASK-007): a
  `worker start` command that takes a task from the GitHub queue to an
  open pull request —
  `TASK → CLAIM → BRANCH → CLAUDE → TEST → HISTORY → PR`. Claims and
  verifies (ADR-0003), gates on dependencies and authorization, enforces
  the task's `allowed_paths`, builds a bounded context pack, runs the
  Claude Code CLI, validates (formatter → lint → types → unit →
  integration), writes the handoff and `history/ai-activity/` entry, and
  opens a PR. It never touches `main` and never merges (ADR-0005).
  Setup and operation: `docs/orchestration/worker-setup.md`.
- **Real task queue** (`orchestrator/task_queue/backlog.py`): 55 tasks
  covering domain, data, detection, graph, agent, tools, API, frontend,
  testing and infrastructure, defined as data and rendered into both the
  `tasks/` mirror and the GitHub issues by
  `scripts/orchestration/seed_backlog.py` (idempotent). `validate()`
  refuses a graph with an unknown dependency or a cycle, and refuses two
  concurrently-claimable tasks that declare overlapping `allowed_paths`
  — the merge conflict no claim protocol can prevent.
- **Continuous worker loop** (ADR-0006): `worker start --continuous`
  propagates human merges into task state so dependants unlock
  (`completion.py`), works through BLOCKED/PROPOSAL outcomes instead of
  idling the machine, polls with jitter when the queue is dry, and
  expires a claim whose issue has been silent for three hours so a
  crashed worker does not strand a task. Bounded by `--max-tasks`,
  `--max-runtime`, `--max-idle` and a three-failure circuit breaker.
  Merge authority is unchanged: a human still merges every PR.
- All 31 repository labels, and `list_issues` pagination — a
  single-page read silently drops tasks past ~100 issues, which is
  indistinguishable from an empty queue.
- Provider routing with `ROUTING_EVENT` logging and a per-call usage
  ledger (`orchestrator/routing/`), plus the handoff schema
  (`orchestrator/policies/task-result.schema.json`).
- Test suite grown from 28 to 446 passing tests, covering the claim race,
  scope enforcement, dependency gating, validation honesty, the merge
  policy, and the whole loop end to end offline — plus an opt-in
  integration test that drives the worker with the **real** Claude Code
  CLI (`WORKER_LIVE_AI_TEST=1`, skipped in CI so it stays free).

## In progress

Nothing is claimed. The queue is seeded and waiting for workers.

`TASK-007` is merged (PR #9). The repository chain is reconciled —
`main` → bootstrap → worker/control plane → real task queue — with both
source branches preserved and no history rewritten.

The critical-path tasks are unstarted. Four are claimable right now, and
they were chosen to have no overlapping `allowed_paths` so four machines
can take one each.

## Blocked

- **Official challenge PDF not available to this session.** All
  scoring-specific requirements are inferred from the working project
  brief. Reconcile against the real PDF before freezing anything in
  `docs/challenge/` as final — see `docs/challenge/README.md`.
- **Branch protection is still not configured.** `main` has no required
  review or status check, so nothing but convention stops a direct push.
  `scripts/setup/branch_protection.sh` needs a human with repo-admin `gh`
  access to run once.
- **No GitHub Project board.** Not required: `tasks/BACKLOG.md` carries
  the index and the dependency graph, and the issues carry the state.

Resolved since the last update: **repository labels now exist.** All 31
were created through the REST API, which accepts them with an ordinary
repo-scoped token even though this session's MCP tool surface has no
label-admin endpoint. The worker's label-less fallback is no longer the
only path, and `worker status` filters on `status:ready` as designed.

## Known bugs

None yet — no runtime code exists.

## Active decisions

See `DECISIONS.md` for the index; full records in `history/decisions/`.
Frozen for this build: PostgreSQL (not Mongo/Snowflake), NetworkX (not a
graph DB), Gemini with function calling (not a full multi-agent framework),
custom bounded agent loop (LangGraph optional/deferred), Solana/ElevenLabs
optional and outside the critical path.

## Open decisions

- Exact Gemini model tier assignment per agent step (Flash vs. Pro) once
  real latency/cost numbers exist.
- Whether LangGraph becomes necessary — revisit only if the custom agent
  loop is visibly hard to maintain after the first vertical slice
  (`ARCHITECTURE.md` §6, operating pack §12).
- Whether to introduce a graph database — only if NetworkX proves too slow
  on the real/synthetic dataset size.
- Whether the development worker should wait for CI and auto-merge
  pre-authorized simple tasks. The policy gate exists and is tested
  (ADR-0005); nothing enables it today, and the default stays "a human
  merges."
- Final frontend graph library choice (Cytoscape.js is the default; not
  yet spiked).

## Next authorized tasks

The full backlog is `tasks/BACKLOG.md` (index + dependency graph),
mirrored in `tasks/ready/` and authoritative as GitHub issues: 55 tasks,
39 of them P0.

Claimable immediately, one per machine:

| Task | Area | Why it is first |
|---|---|---|
| `TASK-001` | data | Canonical entities — nearly everything depends on it |
| `TASK-006` | frontend | Shell against the mocked API; needs no backend |
| `TASK-052` | infra | One-command local stack; no code dependencies |
| `TASK-053` | infra | Environment preflight; no code dependencies |

The critical path to the end-to-end demo (`TASK-049`) is 7 merges:

```
TASK-001 → TASK-002 → TASK-009 → TASK-005 → TASK-025 → TASK-026 → TASK-049
```

That chain is the schedule risk. Everything else fans out from it and
parallelises across machines; nothing shortens it except merging those
seven promptly. **Review latency on those PRs is the project's critical
path**, not worker throughput.

Run a machine with:

```bash
worker status                  # what is eligible, and why the rest is not
worker start --once --dry-run  # rehearse
worker start --continuous --max-runtime 480
```

## Demo readiness

**Not demoable yet.** No detector, agent, or UI exists. The critical path
to a first demoable vertical slice is `ARCHITECTURE.md` §12; do not start
sponsor-integration work (Solana, ElevenLabs) before that slice exists end
to end, per the operating pack's "first 3 hours" plan.
