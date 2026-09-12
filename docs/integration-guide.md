# Integration guide

How to plug a new module implementation in without breaking parallel work.

## Before writing code

1. Find your task in `tasks/ready/` and claim it (`tasks/README.md`).
2. Read the contract(s) your task touches in `docs/contracts/`. If your
   task requires changing one, stop and get human authorization first
   (`CONTRIBUTING.md` §5) — don't build against a contract you're about to
   change.
3. Check `PROJECT_STATE.md` → "In progress" so you don't duplicate work
   another worker already claimed.

## While building

- Stay inside your task's `allowed_paths`. If you discover you need to
  touch something outside them, stop and either get the change
  authorized or hand off a note for the owning module instead of
  editing it yourself (`CONTRIBUTING.md` §4).
- Build against mocks where the real dependency isn't ready yet
  (`docs/contracts/api.md` for frontend-against-backend,
  `docs/contracts/agent-tools.md` for agent-against-data).
- Record a real integration point in `history/integration-log/` the first
  time your module actually talks to another live module (not a mock).

## When done

Follow `CONTRIBUTING.md` §6 (definition of done) and the AI task execution
protocol if you're an AI worker: `orchestrator/README.md` →
"AI task execution protocol."
