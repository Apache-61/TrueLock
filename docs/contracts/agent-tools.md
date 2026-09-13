# Contract: Agent tools

The forensic agent never receives unrestricted SQL (`docs/architecture.md`,
`SECURITY.md`). It receives a fixed, typed tool surface. This is that
surface — the function-calling schema Gemini is given.

## Tool list (minimum executable surface — Hito A)

The full fourteen-tool catalogue is deferred. The current allowlist is:

```
trace_outgoing_funds(account_id, max_depth?) -> Transaction[]
inspect_counterparties(rfcs) -> Counterparty[]
inspect_invoices(provider_rfc) -> Invoice[]
check_regulatory_status(rfc) -> EfosStatus
calculate_exposure(root_transaction_id, returned_transaction_id?) -> Exposure
```

Aliases accepted at the boundary (normalized before execution):

- `account_no` → `account_id`
- `max_hops` / `depth` → `max_depth`

`max_depth` defaults to 3 and is capped at 5.

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
Validation or execution failures still return this envelope with
`errors` set and `result` null.

## Implementation constraints

- Read-only. No tool may write to the database or to this repository
  (`SECURITY.md` → "The forensic agent's authority").
- Each tool is implemented in `backend/src/truelock/agent/tools.py` and covered
  by contract and unit tests that check response shapes match this doc.
- `max_depth` / similar bounds exist on graph-traversal tools so the agent
  cannot accidentally walk the entire graph on one call — bound the blast
  radius of a single tool call.

## Ownership

Forensic Agent Tool Layer (`backend/src/truelock/agent/tools.py`).
