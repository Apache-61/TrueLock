# agent/runtime/

**Purpose:** implements the bounded investigation loop
(`docs/investigation/protocol.md`) — the code that takes a `Lead`, calls
tools, and produces `InvestigationStep`/`Evidence` records until it
`CONCLUDE`s, `DISCARD`s, or `ESCALATE`s.

**What goes here:** the loop/state-machine implementation, hop-limit and
step-budget enforcement, structured-output parsing/validation against
`domain/schemas/investigation_step.schema.json`.

**What does not go here:** the tools themselves (→ `agent/tools/`),
prompt text (→ `agent/prompts/`).

**Depends on:** `agent/tools/`, `agent/prompts/`,
`docs/investigation/protocol.md`, `docs/contracts/investigation.md`.
