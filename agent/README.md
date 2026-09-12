# agent/

**Purpose:** the forensic investigator — the only part of the system that
calls an LLM to reason over financial evidence. Read-only access to data
(`SECURITY.md`), typed tools only (`docs/contracts/agent-tools.md`), never
write access to this repository.

**What goes here:** `runtime/` (the bounded investigation loop,
`docs/investigation/protocol.md`), `prompts/` (system prompts — kept
separate from the *development*-AI prompts used to build this repo, per
`ARCHITECTURE.md` §6/§57), `tools/` (typed tool implementations backing
`docs/contracts/agent-tools.md`), `policies/` (what the agent may/may not
decide — the determinism/AI boundary from `ARCHITECTURE.md` §2).

**What does not go here:** detection rules (`detection/`), evidence-chain
persistence (`evidence/` — the agent produces evidence, `evidence/`
assembles/stores it), anything that writes to the database or this repo.

**Depends on:** `docs/contracts/agent-tools.md`,
`docs/contracts/investigation.md`, `docs/investigation/protocol.md`,
`research/ai/README.md`.

**Owner:** Agent D (Agent/Evidence). Must not touch: `database/**`,
`frontend/**` (`CONTRIBUTING.md` §4).

Empty at bootstrap time — see `tasks/ready/TASK-005-agent-tools.md`.
