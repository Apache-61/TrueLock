# Project State

> The detailed, structured snapshot of where TrueLock stands. Read this
> before doing anything else — it exists so a new contributor (human or AI)
> can get oriented without reading the whole conversation history. For a
> one-glance pulse check instead, see `STATUS.md`. Update this file as part
> of any task that changes what's implemented, blocked, or decided.

**Last updated:** 2026-09-12 · **Updated by:** bootstrap (repository
infrastructure pass)

## Current version

`v0.0.0-bootstrap` — no product code yet. This is the repository
infrastructure/coordination layer only.

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

## In progress

Nothing — this bootstrap pass is the first commit. The first real
implementation tasks are queued in `tasks/ready/` (see also the GitHub
issues opened alongside this commit).

## Blocked

- **Official challenge PDF not available to this session.** All
  scoring-specific requirements are inferred from the working project
  brief. Reconcile against the real PDF before freezing anything in
  `docs/challenge/` as final — see `docs/challenge/README.md`.
- **GitHub repo-admin actions this session could not perform**: creating
  labels, setting branch protection rules, and creating a GitHub Project
  board. The MCP GitHub tool surface available to this session exposes
  issue/PR/file operations but no label-admin or branch-protection
  endpoints. Scripts are provided
  (`scripts/setup/create_labels.sh`, `scripts/setup/branch_protection.sh`)
  for a human with repo-admin `gh` access to run once. See "Known
  limitations" in the bootstrap handoff (`history/ai-activity/`).

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
- Final frontend graph library choice (Cytoscape.js is the default; not
  yet spiked).

## Next authorized tasks

See `tasks/ready/` and the mirrored GitHub issues. In dependency order:

1. `TASK-001` — Canonical domain data ingestion & normalization (Agent B)
2. `TASK-002` — Database schema migration from `database/migrations/0001_init.sql` + seed fixtures (Agent B)
3. `TASK-003` — Synthetic scenario generator using AMLSim-style patterns + one hand-built fraud ring, with an answer key (Agent C)
4. `TASK-004` — Detector framework + first 3 deterministic detectors (duplicate invoice, invoice-payment mismatch, 69-B correlation) (Agent C)
5. `TASK-005` — Agent tool implementations backing `docs/contracts/agent-tools.md` (Agent D)
6. `TASK-006` — Frontend shell against the mocked API contract (Agent A)
7. `TASK-007` — Orchestrator worker adapters (Claude/Gemini) on top of `scripts/orchestration/task_cli.py`

## Demo readiness

**Not demoable yet.** No detector, agent, or UI exists. The critical path
to a first demoable vertical slice is `ARCHITECTURE.md` §12; do not start
sponsor-integration work (Solana, ElevenLabs) before that slice exists end
to end, per the operating pack's "first 3 hours" plan.
