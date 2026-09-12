# Contributing to TrueLock

This repository is built in parallel by several people and several AI
workers across four machines during a 31-hour hackathon. These rules exist
so that parallel work doesn't collide, and so anyone (human or AI) can pick
up a task with only the repository as context.

## 0. Before you touch anything

1. Read `PROJECT_STATE.md` — what's implemented, in progress, blocked.
2. Read `ARCHITECTURE.md` — the frozen decisions. Don't re-litigate them
   here; if one seems wrong, open a `type:decision` issue instead of
   silently deviating.
3. Read `tasks/README.md` and find or claim a task. Don't start
   unscoped work.

## 1. Worker identity

Every machine/session gets a **WORKER_ID** (`WORKER-01` … `WORKER-04`,
or a descriptive slug), set once per machine:

```bash
export WORKER_ID="WORKER-01"
```

Never use only your GitHub username as worker identity — two people can
share a GitHub account or push through the same bot token, and the claim
protocol (`tasks/README.md` §Claim protocol) needs a stable identity that
is not the account name. See `docs/orchestration/worker-setup.md`.

## 2. Claiming a task

Do not start work on a task just because it reads `status:ready`. Two
workers can read that at the same instant. Follow the two-step
**CLAIM → VERIFY** protocol in `tasks/README.md` before writing any code.
If you lose the race, abandon the task immediately and claim a different
one — do not "also" work on it "just in case."

## 3. Branching

Never commit directly to `main`. One branch per task:

```
feature/TASK-###-short-name
research/TASK-###-topic
fix/TASK-###-short-name
experiment/TASK-###-name
```

Keep branches short-lived. `main` is always demoable — do not merge
anything that breaks the last known-good demo path.

## 4. Ownership boundaries

Each area has a primary owner (see `.github/CODEOWNERS` and
`docs/contracts/`). Respect the **allowed / forbidden paths** declared on
your task:

| Owner | Allowed | Must not touch |
|---|---|---|
| Frontend (Agent A) | `frontend/**`, `docs/contracts/api.md` | `domain/**`, `detection/**`, `database/**`, `agent/**` |
| Data/Backend (Agent B) | `backend/**`, `database/**`, `data/**`, `domain/schemas/**` | `frontend/**`, `agent/**`, `detection/rules/**` |
| Detection/Graph (Agent C) | `detection/**`, `tests/scenarios/**`, `domain/entities/**` | `frontend/**`, `agent/**` |
| Agent/Evidence (Agent D) | `agent/**`, `evidence/**`, `docs/investigation/**` | `database/**`, `frontend/**` |

Changing a domain contract (`domain/schemas/**`, `docs/contracts/**`)
requires the human authorization step below — it affects every module.

## 5. Human authorization required for

- changing a domain contract or its JSON Schema;
- changing architecture (`ARCHITECTURE.md`);
- adding a new infrastructure dependency or paid service;
- changing security policy (`SECURITY.md`);
- a database migration that affects existing data;
- changing what authority the forensic agent has;
- deploying to the demo environment;
- merging a PR flagged high-risk.

Everything else (formatting, linting, test runs, dataset validation, docs
checks, local builds, opening issues, drafting PR descriptions, retrying a
transient API error, moving an approved task into execution) can proceed
without waiting for a human.

## 6. Definition of done for any task

1. Code/docs match the task's declared `allowed_paths` — nothing else
   changed.
2. Acceptance criteria in the task are met.
3. Tests for the touched area pass (`pytest`, contract tests, or the
   relevant scenario fixture).
4. A `task-result.json` handoff is written (see
   `docs/contracts/investigation.md`-style handoff format in
   `orchestrator/README.md`) or, at minimum, the PR description covers the
   same fields: summary, changed files, tests, blocking reason (if any),
   next recommended task.
5. `history/timeline.md` gets one line; `history/ai-activity/` gets an
   entry if the task was executed by an AI worker.
6. PR opened against `main`, not pushed directly.

## 7. Two kinds of intelligence — keep them separate

```
FORENSIC INTELLIGENCE   = the investigator agent, reasoning over financial evidence
DEVELOPMENT INTELLIGENCE = AI workers building this repository
```

Never give a development AI worker authority over a forensic conclusion.
Never let the forensic agent modify this repository. Neither may bypass the
contracts in `docs/contracts/`.

## 8. Style

- No commented-out code, no TODO-and-abandon. If something is
  intentionally incomplete, say so in the module's README and in
  `PROJECT_STATE.md`, not as a silent gap.
- Prefer the boring, explainable option over the clever one — this system
  has to survive a judge asking "why."
