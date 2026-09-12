# Changelog

Records product-relevant changes — new capabilities, contract changes,
architecture shifts. Not every commit, not every typo fix; if it wouldn't
matter to someone re-reading this in a week, it doesn't go here.

## [Unreleased]

### Added
- Repository bootstrap: governance docs (`ARCHITECTURE.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `PROJECT_STATE.md`, `STATUS.md`,
  `DECISIONS.md`), full module directory scaffold, domain contracts
  (JSON Schema + docs), task queue with claim/verify-claim protocol,
  GitHub governance files (CODEOWNERS, PR/issue templates, CI baseline),
  and the orchestrator claim-protocol script.

- AI development worker (`orchestrator/workers/`): a `worker start`
  command that claims a task from the GitHub queue, creates an isolated
  branch, runs the Claude Code CLI against a bounded context pack,
  enforces the task's `allowed_paths`, runs the validation gates, writes
  the handoff and history entry, and opens a pull request. Safety limits
  (`--once`, `--continuous`, `--max-tasks`, `--max-runtime`,
  `--dry-run`); never touches `main`, never merges (ADR-0005).
  See `docs/orchestration/worker-setup.md`.
- Provider routing with `ROUTING_EVENT` logging and a per-call usage
  ledger (`orchestrator/routing/`).
- **Canonical domain layer** (TASK-001): `domain/entities/` (six
  validated Pydantic records mirroring `domain/schemas/`),
  `scripts/ingest/` (CFDI 4.0 XML and bank-CSV normalizers that reject
  rather than guess, and report every rejection), and
  `backend/repositories/` (the read surface as `Protocol`s with no
  database dependency, plus in-memory implementations everything
  downstream can develop against before the database lands).
- **Real task queue**: 55 tasks covering domain, data, detection, graph,
  agent, tools, API, frontend, testing and infrastructure, defined in
  `orchestrator/task_queue/backlog.py` and rendered into both the
  `tasks/` mirror and GitHub issues by
  `scripts/orchestration/seed_backlog.py` (idempotent). The graph is
  validated: no unknown dependency, no cycle, and no two
  concurrently-claimable tasks writing the same paths. Index and
  dependency graph in `tasks/BACKLOG.md`.
- **Continuous worker mode** (`worker start --continuous`, ADR-0006):
  propagates human merges into task state so dependent tasks unlock,
  continues past BLOCKED/PROPOSAL outcomes, polls with jitter when the
  queue is dry, and expires a claim whose issue has gone silent so a
  crashed machine does not strand a task. New bounds `--max-idle`,
  `--max-failure-streak`, `--stop-on-blocker`. Merge authority is
  unchanged — a human still merges every PR (ADR-0005).
- Handoff contract `orchestrator/policies/task-result.schema.json`,
  validated against real worker output in `tests/contract/`.
- Opt-in live test driving the worker with the real Claude Code CLI
  (`WORKER_LIVE_AI_TEST=1`; skipped in CI). See `docs/testing.md`.

### Fixed
- **The worker looked hung while it was working.** The AI step is the
  slow one — minutes, with an hour's budget — and the CLI is invoked with
  `capture_output=True` and `-p --output-format json`, so nothing reached
  the terminal until it exited. An operator could not tell a working
  worker from a hung one. It now says the step is silent and slow before
  starting it, and prints elapsed time every 30 seconds while it runs.
- **Ctrl+C stranded the task.** The interrupt handler printed "nothing
  further was changed" while the CLAIM comment was already on the issue,
  so the task stayed locked to a worker that was no longer running until
  the three-hour staleness window expired. An interrupt now releases the
  claim, returns the task to `status:ready`, and says so on the issue —
  and the message no longer claims nothing happened.
- **The worker wedged itself after any failed run.** The failure path
  wrote `history/ai-activity/<run>.md` and appended to
  `history/timeline.md` — both tracked — and committed neither. The next
  run refused to start ("working tree is dirty"), failed, and wrote
  another pair. One transient failure permanently stopped the machine,
  and in `--continuous` it tripped the three-failure circuit breaker with
  two failures the worker had caused itself. Failure handoffs now go to
  `.state/` (gitignored and excluded from the clean check), no timeline
  line is written for a run that produced no branch, and the checkout
  returns to the base branch.
- **The Claude Code adapter could not send its prompt on Windows.**
  `subprocess.run(text=True)` uses the platform's preferred encoding —
  cp1252 on a default Windows install — and the prompt carries this
  repository's own documents, arrows and all. `stdin.write` raised
  `UnicodeEncodeError` on subprocess's writer thread, so `run` did not
  raise: the CLI simply received no input and exited 1 with "Input must
  be provided either through stdin or as a prompt argument", which reads
  like a CLI bug rather than a local encoding problem. The adapter now
  pipes UTF-8 explicitly.
- **A flaky run removed a task from the queue.** Any failure marked the
  issue `status:blocked`, which `dependencies.check_eligibility` treats
  as terminal — so an adapter or network failure dropped a critical-path
  task until a human relabelled it by hand. Infrastructure failures
  (adapter, branch creation, push) now return the task to `status:ready`;
  task-level failures still block for a human.
- The worker no longer overstates what the AI reported: a self-declared
  `PARTIAL`, or a run the AI flagged for human review, opens a clearly
  labelled draft PR instead of a merge-ready one.
- Errors the Claude Code CLI reports in its result envelope while still
  exiting 0 are now detected, and denied tool-permission requests are
  recorded and force human review.
- Worker scratch (`.state/`, and the `__pycache__`/cache directories its
  own validation run creates) is never committed into a task branch and
  never counts as a dirty working tree, regardless of the repository's
  `.gitignore`.

No forensic-agent, detector, or frontend functionality exists yet — this
release is infrastructure and automation only.
