# agent/policies/

**Purpose:** the explicit, documented boundary of what the forensic agent
may decide vs. what must stay deterministic
(`ARCHITECTURE.md` §2, `history/decisions/ADR-0002-determinism-ai-split.md`).

**What goes here:** the policy list itself (as config or code — TBD by
`TASK-005`), plus any per-lead budget/threshold the agent runtime enforces
(step budget, hop limits — `docs/investigation/protocol.md` §Termination
guarantees).

**What does not go here:** the loop implementation (→ `agent/runtime/`),
detector thresholds (→ `detection/scoring/`, a separate deterministic
boundary).

**Depends on:** `ARCHITECTURE.md` §2, `SECURITY.md`.
