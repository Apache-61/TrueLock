# Contract: Case

Schema: `domain/schemas/case.schema.json`. The final, judge-facing
artifact — see `docs/demo/runbook.md` steps 9-12.

## Example

```json
{
  "case_id": "CASE-001",
  "status": "SUBSTANTIATED",
  "hypothesis": "Circular movement of supplier funds",
  "amount_involved": 1842000,
  "supporting_evidence": ["E-001", "E-014", "E-019"],
  "discarded_leads": [
    { "lead_id": "L-004", "reason": "Isolated late payment, no corroborating signal" }
  ],
  "confidence_level": "HIGH",
  "limitations": ["No direct beneficial-owner record available"],
  "citations": ["CFF Art. 69-B"]
}
```

## Status is one of three, never a bare "suspicious"

- `SUBSTANTIATED` — the accumulated evidence supports the hypothesis.
- `UNSUBSTANTIATED` — investigated, and the evidence does not support it
  (this is a real, useful outcome — the system must be able to say "we
  looked, and it's clean").
- `INSUFFICIENT_EVIDENCE` — investigation is incomplete or blocked (e.g.
  missing beneficial-owner records); says what's missing in `limitations`.

## Required fields and why

- `discarded_leads` — every lead considered and not pursued, with reason.
  This is the "what did you rule out" the challenge brief requires.
- `limitations` — what's missing, and (implicitly) what would change the
  conclusion. Directly answers `docs/demo/runbook.md` step 12: "What would
  change your conclusion?"
- `citations` — regulatory/rule references, so "why is this relevant"
  always traces to something outside the model's own say-so.
- `evidence_hash` — optional; if Solana notarization is wired
  (`history/decisions/ADR-0004-sponsor-tech-scope.md`), this is the value
  anchored on-chain.

## Who owns this contract

Agent D (Agent/Evidence). The API contract for serving/rendering a Case is
`docs/contracts/api.md`.
