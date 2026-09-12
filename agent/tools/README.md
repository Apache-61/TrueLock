# agent/tools/

**Purpose:** the typed, read-only tool surface the agent calls — the exact
implementations backing `docs/contracts/agent-tools.md`.

**What goes here:** one function per tool
(`search_supplier`, `trace_outgoing_funds`, `check_69b_status`, etc.),
each returning the `result/provenance/source_ids/execution_time/errors`
shape, each bounded (e.g. `max_hops`) so a single call can't traverse the
whole graph.

**What does not go here:** unrestricted SQL access, write operations of
any kind (`SECURITY.md`), reasoning about which tool to call (→
`agent/runtime/`).

**Depends on:** `backend/repositories/`, `detection/graph/`,
`docs/contracts/agent-tools.md`.
