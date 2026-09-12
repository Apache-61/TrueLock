# TrueLock — The Forensic Auditor

TrueLock is our entry for the Infosys **"The Forensic Auditor"** track: an AI
system that does not just flag anomalies in invoices and payments, it
**investigates** them — follows leads, traces money, builds an auditable
evidence chain, and produces a case file a human auditor can interrogate.

> This repository is currently in **bootstrap / infrastructure phase**. The
> forensic agent, detectors, and frontend are not implemented yet. What
> exists is the shared contracts, task system, and governance that let
> several people/AIs build those modules in parallel without colliding.
> See [`PROJECT_STATE.md`](PROJECT_STATE.md) for exactly what is and isn't
> built.

## Start here

| If you want to... | Read |
|---|---|
| Understand the product thesis and stack decisions | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| See what's built, in progress, or blocked right now | [`PROJECT_STATE.md`](PROJECT_STATE.md) |
| See why a technical choice was made | [`DECISIONS.md`](DECISIONS.md) |
| Pick up work as a contributor (human or AI) | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Understand the data contracts between modules | [`docs/contracts/`](docs/contracts/) |
| Understand the regulatory grounding (SAT / CFDI / 69-B) | [`docs/regulatory/`](docs/regulatory/) |
| See the demo script for judges | [`docs/demo/runbook.md`](docs/demo/runbook.md) |
| Find a task to work on | [`tasks/README.md`](tasks/README.md) |

## Core thesis

The system is not a classifier that outputs "supplier X is suspicious." It
is a chain of reasoning:

```
signal → lead → decision to pursue/discard → evidence → relationship →
money flow → amount → hypothesis → conclusion (with confidence level)
```

Every step must point back to a concrete source record or rule. Detection,
scoring, and money-flow tracing are **deterministic** (auditable, testable);
the LLM layer investigates, explains, and answers questions — it never
invents facts. See `ARCHITECTURE.md` §2 for the full rationale.

## Repository shape

```
docs/          regulatory + contract + detection + investigation + demo docs
research/      source material and stack research backing the decisions
domain/        canonical entities, JSON-schema contracts, enums
detection/     deterministic fraud-pattern detectors and scoring
agent/         investigator runtime, tools, prompts, policies
evidence/      evidence chain and case-file assembly
database/      schema migrations and seed data
backend/       API + services + repositories
frontend/      investigation UI
data/          raw / normalized / synthetic / fixture datasets + answer keys
tests/         unit, contract, integration, e2e, scenario tests
orchestrator/  AI-worker task queue, routing, claim protocol
tasks/         the task queue itself (see tasks/README.md)
history/       decisions, changes, experiments, timeline — engineering memory
scripts/       ingestion, validation, demo, orchestration, setup scripts
```

Each directory with meaningful content has its own `README.md` explaining
its purpose, what belongs there, what doesn't, and what depends on it.

## Working on this repo

Never commit directly to `main`. Every task gets its own branch
(`feature/TASK-###-slug`, `research/...`, `fix/...`, `experiment/...`) and a
PR. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`tasks/README.md`](tasks/README.md) for the full workflow, the task state
machine, and the claim protocol that stops two workers from picking up the
same task.
