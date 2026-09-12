# agent/prompts/

**Purpose:** system prompts for the *forensic* agent only.

**What goes here:** the investigator's system prompt, structured-output
schema instructions, and any few-shot examples grounding it in
`docs/regulatory/` and `docs/detection/rules.md`.

**What does not go here:** prompts for *development* AI workers building
this repository — those are a separate, never-mixed concern
(`ARCHITECTURE.md` §6, `history/decisions/ADR-0002-determinism-ai-split.md`).
If a development-worker prompt is ever needed, it belongs under
`orchestrator/`, not here.

**Depends on:** `docs/regulatory/`, `docs/detection/rules.md`,
`docs/contracts/investigation.md`.
