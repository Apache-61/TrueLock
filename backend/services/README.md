# backend/services/

**Purpose:** business logic that assembles a response from one or more
repositories/modules — e.g. building the `/graph/:case_id` view from the
domain graph, or triggering an investigation run.

**What goes here:** orchestration code that calls `backend/repositories/`,
`detection/`, or `agent/` and shapes the result to `docs/contracts/api.md`.

**What does not go here:** detection rules or agent reasoning themselves
(those modules own their own logic; services call them, not reimplement
them). No direct SQL — go through `backend/repositories/`.

**Depends on:** `backend/repositories/`, `detection/`, `agent/`,
`docs/contracts/`.
