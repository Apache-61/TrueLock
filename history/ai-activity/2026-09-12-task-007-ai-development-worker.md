# 2026-09-12 — TASK-007: AI development worker MVP

- **task_id:** TASK-007 (issue
  [#7](https://github.com/Apache-61/TrueLock/issues/7))
- **worker:** Claude Code session (`session_01XHrhL745mvhCbE5Cq6WvdC`),
  human-directed — this entry records a session commissioned directly by
  the repository owner, not an autonomous `worker start` run
- **branch:** `claude/vigilant-hamilton-6u3jg6` (based on the bootstrap
  branch `claude/vigilant-noether-yzghll`, since `main` still carries only
  the initial commit)
- **start:** 2026-09-12
- **end:** 2026-09-12
- **result:** DONE — 334 tests passing, PR opened, not merged

## Goal

Implement the first MVP of the AI development worker: let a teammate's
machine run `worker start` and have it identify itself, read the GitHub
task queue, pick an eligible READY task by priority, claim it without
colliding with another worker, branch, run Claude Code against a bounded
context, validate, record a handoff and history entry, and open a pull
request — then look for the next task.

This is `tasks/ready/TASK-007-orchestrator-worker-adapters.md`, which is
marked `execution_mode: human`. The authorization was given directly by
the repository owner; see
`history/decisions/ADR-0005-ai-development-worker.md`.

## Summary

`orchestrator/workers/` now implements the full protocol from
`orchestrator/README.md`:

```
TASK → CLAIM → BRANCH → CLAUDE → TEST → HISTORY → PR
```

Five boundaries are enforced in code rather than left to convention,
because an unattended worker gets no chance to notice it crossed one:

1. **Two workers never execute one task.** Claiming is posting *and*
   re-reading; the earliest live claim by GitHub comment ID wins
   (ADR-0003). A worker that loses writes no code and withdraws its claim.
   RELEASE is honoured, so a released task can be re-claimed rather than
   being owned forever by a stale first claim.
2. **Scope is a hard stop.** A change outside the task's `allowed_paths`
   blocks the task and reports what is missing; the worker never widens
   its own scope. Forbidden beats allowed; a task declaring no
   `allowed_paths` may change nothing.
3. **`main` is untouchable and nothing is merged.**
4. **A failing or unverified run never looks like a passing one.** A
   skipped gate is not a pass; a change nothing ran against opens as a
   draft PR marked `[UNVERIFIED]`, a failing one as `[VALIDATION FAILED]`.
5. **`execution:human` means propose, not implement.** The worker posts a
   proposal, releases the task, and writes no file.

## Changes

New (`orchestrator/workers/`): `cli.py`, `runner.py`, `config.py`,
`github.py`, `tasks.py`, `claim.py`, `dependencies.py`, `scope.py`,
`gitops.py`, `context.py`, `validation.py`, `handoff.py`,
`pullrequest.py`, `merge_policy.py`, `safety.py`, `adapters/{base,
claude_code,mock}.py`.

New (`orchestrator/routing/`): `router.py` (provider selection +
`ROUTING_EVENT` logging), `ledger.py` (per-call usage ledger).

New elsewhere: `orchestrator/policies/task-result.schema.json`,
`scripts/orchestration/worker.py` and the `worker` shim,
`docs/orchestration/worker-setup.md`,
`history/decisions/ADR-0005-ai-development-worker.md`, seven test modules,
root `conftest.py`.

Updated: `orchestrator/README.md` and the `workers/`, `routing/`,
`policies/`, `state/` READMEs; `PROJECT_STATE.md`, `STATUS.md`,
`CHANGELOG.md`, `DECISIONS.md`, `.env.example`; the TASK-007 mirror moved
to `tasks/active/`.

## Tests

`pytest -q` → **352 passed, 9 skipped, 0 failed** (baseline before this
task: 28). The 9 skipped are the live-AI integration tests, which are
opt-in; with `WORKER_LIVE_AI_TEST=1` they pass too, against the real
Claude Code CLI.

New coverage, by the rule it protects:

| Module | What it pins down |
|---|---|
| `test_worker_claim.py` | the race: four-way contention, out-of-order comment IDs, RELEASE, withdrawal, and wire-format compatibility with `task_cli.py` |
| `test_worker_scope.py` | forbidden beats allowed, empty allow-list permits nothing, `../` and absolute paths are violations |
| `test_worker_dependencies.py` | an unknown dependency counts as unmet; READY_FOR_REVIEW is not MERGED |
| `test_worker_validation.py` | skipped ≠ passed; "nothing ran" reports as NOT VERIFIED |
| `test_worker_safety.py` | destructive-command refusal, run limits, the triple-gated merge policy |
| `test_worker_routing.py` | `ROUTING_EVENT` on every selection; ledger rows match the frozen schema; both YAML readers agree |
| `test_worker_handoff.py` | result parsing (including that unparseable output is an error, not a success), ADR escalation |
| `test_worker_loop.py` | the whole loop offline: happy path, lost claim, `execution:human`, scope violation, validation failure, adapter failure, dry run, limits |
| `test_worker_cli.py` | identity validation, `.env` parsing, argument wiring |
| `tests/contract/test_orchestrator_contracts.py` | worker output still validates against the handoff and ledger schemas |

Also verified against the live repository: `worker doctor` (reaches the
GitHub API, finds 7 open issues, detects the Claude CLI), `worker status`
(reads the real queue and correctly reports TASK-002..005 as blocked on
unmet dependencies), and `worker start --once --dry-run` (full loop, zero
writes).

## Bugs found and fixed while building

Four were found by the tests rather than by reading, and all four would
have been silent in production:

1. `git status --porcelain` collapses a wholly-untracked directory into a
   single `dir/` entry, so the scope guard was judging a directory name
   that no file glob matches. Fixed with `-uall`.
2. `lstrip("./")` strips *characters*, turning `.github/...` into
   `github/...` — every merge-policy and ADR rule keyed on `.github/`
   silently stopped matching. Replaced with an explicit prefix strip.
3. Stripping a `(frozen)` annotation from a path bullet left a trailing
   backtick, producing a glob that matched nothing — a forbidden-path rule
   that never fired.
4. Push retried a permanent failure (no such remote) four times with
   exponential backoff. Now only genuinely transient failures are retried.

## Follow-up: live verification against the real Claude Code CLI

The first version of this work was tested entirely offline, and the
handoff listed "the Claude Code adapter has not been exercised against a
paid API" as its main open risk. That has now been closed: the whole loop
was run against the real CLI in a throwaway repository, with a small but
genuine task ("add a `median()` helper with tests"). It is captured as an
opt-in test, `tests/integration/test_worker_live_claude.py`, skipped
unless `WORKER_LIVE_AI_TEST=1` so CI stays free and fast.

**It worked** — claim → branch → real Claude Code → validation → draft or
normal PR, with real token usage in the ledger ($0.24, 4.3k output tokens,
model recorded as `claude-sonnet-5`). The AI's code was correct: the test
runs `median()` itself rather than trusting the status that came back.

It also surfaced five defects that no amount of offline testing would
have found, because each depended on what the real CLI actually does:

1. **A self-declared PARTIAL was promoted to DONE** whenever validation
   happened to pass. Passing tests prove that what was written works, not
   that what was asked for got written. `PARTIAL` is now its own outcome
   and opens a draft PR titled `[PARTIAL]`.
2. **A run the AI explicitly flagged `requires_human_review` opened as a
   normal, merge-ready PR.** It is now a draft titled
   `[NEEDS HUMAN REVIEW]`, with the AI's reasons in the risks section.
3. **`is_error` in the CLI envelope was ignored.** The CLI can report a
   failure while still exiting 0, so trusting the exit code alone turned
   a failed run into a confident DONE.
4. **Permission denials were invisible.** In the first live run the CLI
   denied 8 of the AI's `Bash` requests, so it could not run the tests it
   wrote — and said so honestly in its summary. The worker now records
   denials, appends them to known issues, and forces human review. (The
   design held up here: the worker runs the validation gates itself, so
   the AI being unable to run tests did not produce a false pass.)
5. **The worker committed its own scratch into the branch.** `.state/`,
   and then `__pycache__/` from its own validation run, were landing in
   the PR in any repository whose `.gitignore` does not cover them —
   which is not something the worker should depend on. Worker artifacts
   are now excluded from commits at any path depth, and excluded from the
   clean-tree check too, so they no longer strand a continuous run after
   one task.

Two of these — 1 and 2 — were the worker overstating what the AI itself
had said, which is precisely the failure mode the rest of the design
guards against. They are now pinned by unit tests as well as the live one.

The ledger also now records the model that actually served the turn
(`modelUsage`) rather than the one requested, since the runtime can fall
back and a row naming the wrong model misattributes the spend.

## Known issues / limitations

1. **Single provider.** Only the Claude Code CLI is wired up; TASK-007
   also names a Gemini adapter. Deferred deliberately — the routing layer,
   `ROUTING_EVENT` logging and usage ledger are built and tested, so
   adding Gemini is a registration rather than a rewrite.
2. **CI is not awaited.** The worker opens the PR and stops. Auto-merge is
   therefore unreachable in practice even when explicitly enabled; the
   policy gate exists so that adding CI-awaiting later cannot quietly
   widen what may be merged.
3. **The adapter is now proven against the real CLI, but not against the
   real repository.** The live test (above) runs the full loop with a
   genuine AI in a throwaway repository and an in-memory GitHub. What has
   still never happened is a live `worker start --once` against
   `Apache-61/TrueLock` itself, which would claim a real issue and open a
   real PR. The first one should be watched by a human.
4. **The CLI's JSON envelope is version-sensitive.** Token counts are read
   from `--output-format json` when present and left null otherwise; the
   worker never estimates a cost. A CLI upgrade that renames those fields
   degrades the ledger rather than breaking the run.
5. **Repository labels still do not exist.** The worker falls back to
   reading task state from issue bodies and treats label updates as
   advisory, so it works — but `scripts/setup/create_labels.sh` should
   still be run by someone with `gh` repo-admin rights.
6. **`main` is one commit behind the project.** The bootstrap branch was
   never merged, so this branch is based on it rather than on `main`. Both
   PRs need merging, bootstrap first.
7. **Scope deviation, declared:** this task's `allowed_paths` cover
   `orchestrator/` and `scripts/orchestration/`, but its own "Tests
   required" and "Documentation requirements" sections oblige it to touch
   `tests/`, `docs/orchestration/`, `history/`, and the root state files,
   plus `orchestrator/__init__.py` and a root `conftest.py` for
   importability. Listed in the task mirror and the PR rather than
   silently widened.

## Next recommended tasks

1. Merge the bootstrap PR, then this one.
2. Run `scripts/setup/create_labels.sh` and
   `scripts/setup/branch_protection.sh` (needs `gh` repo-admin).
3. `TASK-001` (canonical ingestion) — P0, startable now, unblocks
   TASK-002/003/004. Good first candidate for a watched live
   `worker start --once`.
4. `TASK-006` (frontend shell) — P0, no dependencies, can run in parallel
   on a second workstation.

## Requires human review

Yes. This adds infrastructure that runs an AI against the repository
autonomously, which `CONTRIBUTING.md` §5 reserves for human
authorization, and ADR-0005 records the execution model and merge
authority chosen. The boundaries are enforced in code and tested, but the
first live run on a real task is worth watching.
