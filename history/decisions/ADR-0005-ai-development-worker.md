# ADR-0005: AI development worker — execution model and merge authority

**Status:** Accepted
**Date:** 2026-09-12
**Deciders:** repository owner (authorized the execution of
`TASK-007-orchestrator-worker-adapters`, which is marked
`execution_mode: human` / `human_authorization: yes`), implemented by an
AI worker session

## Context

ADR-0003 made GitHub Issues the source of truth for task claims and
`scripts/orchestration/task_cli.py` implemented the claim protocol, but
every other step of the "AI task execution protocol"
(`orchestrator/README.md`) was still manual: a human read the task, ran
the AI, checked the diff, ran the tests, wrote the handoff, and opened
the PR.

TASK-007 asked for the missing piece — worker adapters that do that
automatically — and was explicitly held at `execution: human` because it
is new infrastructure that calls paid APIs autonomously
(`CONTRIBUTING.md` §5). That authorization was given directly, for this
implementation.

The hard question is not "can an AI write the code". It is **what an
autonomous worker is allowed to do when nobody is watching**, on a
repository four workers share.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Keep it manual (status quo) | Zero new risk; a human sees every diff | Does not scale to four parallel workstations; the coordination overhead is the bottleneck the task system exists to remove |
| Full autonomy: worker implements, tests, merges | Fastest throughput | No human ever reads a diff before it reaches `main`; one bad change breaks the demo path for everyone, and `main` must stay demoable (`CONTRIBUTING.md` §3) |
| **Autonomous up to the pull request, never past it** | Removes the repetitive work; every change still gets a human reader; `main` stays protected | A human is still in the loop per task, so review remains the throughput limit |

## Decision

Build the worker to run `TASK → CLAIM → BRANCH → CLAUDE → TEST →
HISTORY → PR` autonomously, and **stop at the pull request**.

Five boundaries are enforced in code rather than documented as
convention, because an unattended worker gets no chance to notice it
crossed one:

1. **Claim before work, verify before code.** A worker that loses the
   race writes nothing (`claim.py`, ADR-0003).
2. **Scope is a hard stop, not a guideline.** A change outside the task's
   `allowed_paths` blocks the task and reports what is missing; the
   worker never widens its own scope (`scope.py`).
3. **`main` is untouchable and nothing is merged** (`gitops.py`,
   `merge_policy.py`).
4. **A failing or unverified run never looks like a passing one.** A
   skipped gate is not a pass, and a change nothing ran against opens as
   a draft (`validation.py`).
5. **`execution:human` means propose, never implement** (`runner.py`).

### On auto-merge

TASK-007's acceptance criterion is "Never auto-merges." The team also
asked for auto-merge to be *possible* for simple, previously authorized
tasks after CI. These are reconciled by making the default absolute and
the exception expensive: `--allow-auto-merge` merges only when a human
passes the flag **and** a human has labelled the task
`execution:auto-merge-approved` **and** the change touches none of
architecture, contracts, schemas, security, migrations, or CI, **and**
the task type is not security/decision/experiment/research.

In this MVP no run reaches a merge, because the worker does not wait for
CI. The gate is built and tested now so that adding CI-awaiting later
cannot quietly widen what may be merged.

### On providers

One provider — the Claude Code CLI. Gemini and multi-provider routing are
deferred on purpose: the end-to-end loop had to work first. The routing
layer, `ROUTING_EVENT` logging and usage ledger are built and tested
against the real policy file, so adding a provider is a registration
rather than a rewrite.

## Consequences

**Easier:** a workstation with a token and a Claude login can run
`worker start --once` and produce a reviewed-ready PR without a human
driving each step. Every run leaves a durable record
(`history/ai-activity/`, the usage ledger, the claim thread), so what an
AI did is auditable after the fact — the same standard `ARCHITECTURE.md`
§1 demands of the forensic side.

**Harder:** review is now the bottleneck, deliberately. Four workers can
generate PRs faster than one human can read them, and the answer is to
read them, not to raise the merge authority.

**Foreclosed:** an AI worker cannot record a decision. Touching
architectural surface raises an ADR requirement and forces human review;
it never writes the ADR itself, because an AI-authored record of a
decision nobody made is worse than no record.

## Reversibility

High. The worker is an operational tool, not a structural dependency:
`scripts/orchestration/task_cli.py` and the manual protocol in
`tasks/README.md` still work unchanged, and nothing else in the
repository imports `orchestrator/workers/`. Deleting it costs nothing
already built.
