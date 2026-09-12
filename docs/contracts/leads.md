# Contract: Lead

Schema: `domain/schemas/lead.schema.json`. Produced by `detection/`,
consumed by `agent/`.

## What a Lead is (and isn't)

A Lead is **"this is worth investigating,"** not **"this is fraud."** It
is the aggregation of one or more `detector_signal` records
(`domain/schemas/detector_signal.schema.json`) that crossed a documented,
deterministic threshold (`docs/detection/rules.md` §Scoring).

```
observed fact → detector_signal → (aggregate + threshold) → Lead
```

## Example

```json
{
  "lead_id": "L-001",
  "entity_id": "SUP-0042",
  "detector_id": "SUPPLIER_CONCENTRATION",
  "reason": "Supplier received unusually concentrated payments",
  "risk_score": 0.82,
  "signals": ["S-14", "S-27"],
  "status": "OPEN"
}
```

## Status lifecycle

```
OPEN → FOLLOWED   (the agent investigated it; see investigation.md)
OPEN → DISCARDED  (deliberately not pursued — discard_reason is required)
```

`discard_reason` must be a citable reason (e.g. "risk_score below the
0.6 pursue threshold with no corroborating signal type"), never "the
model decided it wasn't worth it." This is what lets the system answer a
judge's "why did you discard supplier Y?" (`docs/demo/runbook.md` step 8).

## Who owns this contract

Agent C (Detection/Graph) produces Leads; Agent D (Agent/Evidence)
consumes them. Both must agree on any schema change (human authorization
required, `CONTRIBUTING.md` §5).
