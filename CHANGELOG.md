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
- Handoff contract `orchestrator/policies/task-result.schema.json`,
  validated against real worker output in `tests/contract/`.
- Opt-in live test driving the worker with the real Claude Code CLI
  (`WORKER_LIVE_AI_TEST=1`; skipped in CI). See `docs/testing.md`.

### Fixed
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
