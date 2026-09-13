# Contract: Agent tools

The forensic agent never receives unrestricted SQL (`docs/architecture.md`,
`SECURITY.md`). It receives a fixed, typed tool surface. This is that
surface — the function-calling schema Gemini is given.

## Decision (Fase 2 / Hito A)

The **minimum executable surface is five tools**. The earlier fourteen-tool
catalogue remains deferred; do not invent stubs for tools that are not
implemented and contract-tested.

```
trace_outgoing_funds(account_id, max_depth?) -> Transaction[]
inspect_counterparties(rfcs) -> Counterparty[]
inspect_invoices(provider_rfc) -> Invoice[]
check_regulatory_status(rfc) -> EfosStatus
calculate_exposure(root_transaction_id, returned_transaction_id?) -> Exposure
```

Canonical parameter names:

| Tool | Required | Optional |
|---|---|---|
| `trace_outgoing_funds` | `account_id` | `max_depth` (default 3, cap 5) |
| `inspect_counterparties` | `rfcs` | — |
| `inspect_invoices` | `provider_rfc` | — |
| `check_regulatory_status` | `rfc` | — |
| `calculate_exposure` | `root_transaction_id` | `returned_transaction_id` |

Aliases accepted **only** at the validation boundary (normalized, never
forwarded to handlers):

- `account_no` → `account_id`
- `max_hops` / `depth` → `max_depth`

Undeclared keys, wrong types, missing required fields, and out-of-range
limits are rejected. Rejection still returns the envelope below with
`errors` set and `result` null.

## Every tool returns

```json
{
  "result": "...",
  "provenance": "...",
  "source_ids": ["..."],
  "execution_time": 0.0,
  "errors": null
}
```

`provenance` and `source_ids` are not optional — they are what lets an
Evidence record (`docs/contracts/evidence.md`) trace back to a concrete
source, and what lets the agent answer "where did that come from."

## Implementation constraints

- Read-only. No tool may write to the database or to this repository
  (`SECURITY.md` → "The forensic agent's authority").
- Each tool is implemented in `backend/src/truelock/agent/tools.py` and covered
  by contract and unit tests that check response shapes match this doc.
- `max_depth` bounds graph-traversal blast radius per call.
- Gemini and the deterministic fallback share the same validate → execute
  path; invalid model args never bypass validation.

## Ownership

Forensic Agent Tool Layer (`backend/src/truelock/agent/tools.py`).
