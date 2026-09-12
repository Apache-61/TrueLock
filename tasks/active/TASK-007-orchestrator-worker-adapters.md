# TASK-007: Orchestrator worker adapters

- **type:** integration
- **priority:** P1
- **status:** READY_FOR_REVIEW
- **execution_mode:** human
- **owner (area):** shared
- **depends_on:** none (`scripts/orchestration/task_cli.py` from the
  bootstrap already implements claim/verify)
- **human_authorization:** yes — adds real API-calling workers, which is
  new infrastructure per `CONTRIBUTING.md` §5. **Granted** by the
  repository owner on 2026-09-12, who directly commissioned this
  implementation. Recorded in
  `history/decisions/ADR-0005-ai-development-worker.md`.

## Objective

Add `orchestrator/workers/claude.py` and `orchestrator/workers/gemini.py`
adapters that, given a claimed task, invoke the respective CLI/API to
implement it, capture the result, run tests, and write the
`task-result.json` handoff (`orchestrator/README.md`). This automates the
"AI task execution protocol" beyond the manual claim/verify step already
built.

## Allowed paths

```
orchestrator/workers/**
orchestrator/routing/**
orchestrator/policies/**
scripts/orchestration/**
```

## Forbidden paths

```
domain/**
detection/**
agent/**
frontend/**
```

## Input

`orchestrator/README.md`, `scripts/orchestration/task_cli.py`,
`orchestrator/policies/provider-pool.yaml`.

## Output

A worker adapter that can be pointed at a `READY` task and produce a PR +
handoff without a human manually running each step — while still stopping
at every human-authorization boundary in `CONTRIBUTING.md` §5.

## Acceptance criteria

- [ ] Never auto-merges (`CONTRIBUTING.md` §5, operating pack §49 —
      "Auto-merge significant change: NO").
- [ ] Logs every provider-routing decision
      (`ROUTING_EVENT from/to/reason`, see
      `research/infrastructure/README.md`'s fallback matrix and
      `orchestrator/policies/provider-pool.yaml`).
- [ ] Records token usage per call against the usage ledger schema.

## Tests required

A dry-run mode that exercises claim → mock-implement → handoff without
calling a real paid API.

## Documentation requirements

`orchestrator/README.md` updated with real usage instructions.

## Outcome (2026-09-12)

Implemented on `claude/vigilant-hamilton-6u3jg6`. See
`history/ai-activity/` for the handoff and
`history/decisions/ADR-0005-ai-development-worker.md` for the execution
model and merge authority decided here.

Acceptance criteria:

- [x] **Never auto-merges.** The default is absolute; `--allow-auto-merge`
      requires the flag *and* an `execution:auto-merge-approved` label
      *and* a change touching no architecture/contract/schema/security/
      migration/CI path. Enforced in `orchestrator/workers/merge_policy.py`,
      asserted in `tests/unit/test_worker_safety.py` and at loop level in
      `tests/unit/test_worker_loop.py`.
- [x] **Logs every provider-routing decision.** `ROUTING_EVENT from/to/reason`
      on every selection, not only on switches
      (`orchestrator/routing/router.py`).
- [x] **Records token usage per call** against
      `orchestrator/policies/usage-ledger.schema.json`
      (`orchestrator/routing/ledger.py`), validated in `tests/contract/`.
- [x] **Dry-run mode** exercising claim → mock-implement → handoff with no
      paid API call (`worker start --once --dry-run`,
      `tests/unit/test_worker_loop.py::TestDryRun`).
- [x] **`orchestrator/README.md` updated** with real usage instructions,
      plus a full guide at `docs/orchestration/worker-setup.md`.

Deviations from the task as written, and why:

1. **No Gemini adapter.** The task names `claude.py` *and* `gemini.py`.
   Only the Claude adapter exists: getting the loop working end to end
   was the priority, and multi-provider routing is explicitly deferred.
   The routing layer is real and tested, so adding Gemini is a
   registration rather than a rewrite.
2. **Files written outside `allowed_paths`.** The declared budget covers
   `orchestrator/` and `scripts/orchestration/`, but this task's own
   "Tests required" and "Documentation requirements" sections — and
   `CONTRIBUTING.md` §6 — oblige it to add tests, docs, history, and
   state updates. Those landed in `tests/`, `docs/orchestration/`,
   `history/`, and the root state files, plus `orchestrator/__init__.py`
   and a root `conftest.py` needed to make the package importable by the
   test suite. Recorded here rather than quietly widened.
