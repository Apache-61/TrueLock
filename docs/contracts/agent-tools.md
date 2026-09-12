# Contract: Agent tools

The forensic agent never receives unrestricted SQL (`ARCHITECTURE.md` §6,
`SECURITY.md`). It receives a fixed, typed tool surface. This is that
surface — the function-calling schema Gemini is given.

## Tool list

```
search_supplier(query) -> Provider[]
get_supplier_profile(rfc) -> Provider
get_invoice(uuid) -> Invoice
find_invoice_payments(invoice_uuid) -> Payment[]
find_payments_for_supplier(rfc) -> Payment[]
trace_outgoing_funds(account_no, max_hops) -> Transaction[]
trace_incoming_funds(account_no, max_hops) -> Transaction[]
find_related_entities(entity_id) -> Entity[]
find_graph_path(from_entity_id, to_entity_id) -> Path
find_cycles(entity_id) -> Cycle[]
find_fan_in_fan_out(account_no) -> FanPattern
check_69b_status(rfc) -> EfosStatus
get_source_record(source_type, source_id) -> Record
get_evidence(evidence_id) -> Evidence
```

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
- Each tool is implemented once, in `agent/tools/`, and covered by a
  contract test (`tests/contract/`) that checks the response shape
  matches this doc regardless of which underlying query implementation is
  used.
- `max_hops` / similar bounds exist on graph-traversal tools so the agent
  cannot accidentally walk the entire graph on one call — bound the blast
  radius of a single tool call.

## Who owns this contract

Agent D (Agent/Evidence) defines it; Agent B (Data/Backend) implements the
query layer underneath it.
