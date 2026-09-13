# Contract: Evidence

Schema: `domain/schemas/evidence.schema.json`. Produced by `agent/` tool
calls (via `investigation_step.result_refs`), stored/assembled by
`evidence/`.

## What Evidence is (and isn't)

Evidence is a **sourced, falsifiable claim**, not an interpretation.
"Payment of 842000 MXN occurred on 2026-08-13" is evidence. "This looks
like money laundering" is an inference built *from* evidence, and belongs
in `investigation_step.decision` or the final `case.hypothesis`, never in
an evidence record itself.

## Example

```json
{
  "evidence_id": "E-001",
  "type": "TRANSACTION",
  "source_type": "BANK_RECORD",
  "source_id": "TX-8841",
  "claim": "Payment of 842000 MXN occurred on 2026-08-13",
  "strength": "DIRECT"
}
```

## Strength levels

- **DIRECT** — proves the claim outright (e.g. the transaction record
  itself).
- **CORROBORATING** — supports another piece of evidence but doesn't
  stand alone (e.g. two shell providers sharing a registered address).
- **CIRCUMSTANTIAL** — consistent with the hypothesis but doesn't prove
  it (e.g. unusually fast payment timing, alone).

A `case.status` of `SUBSTANTIATED` should never rest on circumstantial
evidence alone — see `docs/contracts/case.md`.

## Provenance requirement

Every tool in `docs/contracts/agent-tools.md` returns `source_ids`, and
every Evidence record's `source_id`/`source_type` must trace back to one
of those. If a judge asks "where does that number come from," the answer
is always a specific record ID, never "the model computed it."

## Ownership

Evidence Collection Subsystem (`backend/src/truelock/evidence/exposure.py`).
