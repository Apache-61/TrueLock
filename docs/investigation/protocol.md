# Investigation protocol

The bounded loop the forensic agent runs for each Lead. This is a state
machine, not a free-running agent — it must terminate, and every
transition must be explainable.

## Category discipline

The system must never collapse these into each other:

```
observed fact ≠ anomaly ≠ hypothesis ≠ lead ≠ evidence ≠ inference ≠ conclusion
```

| Category | Where it lives | Example |
|---|---|---|
| Observed fact | raw canonical data | "Invoice INV-1 for 250,000 MXN dated 2026-06-15" |
| Anomaly | `detector_signal` | "Amount is 4.2 standard deviations above this supplier's history" |
| Lead | `domain/schemas/lead.schema.json` | "Supplier X is worth investigating (risk_score 0.82)" |
| Evidence | `domain/schemas/evidence.schema.json` | "Payment TX-8841 of 842,000 MXN occurred 2026-08-13" |
| Inference | `investigation_step.decision` + reasoning | "This payment pattern is consistent with layering" |
| Conclusion | `domain/schemas/case.schema.json` | "SUBSTANTIATED: circular movement of funds, 1,842,000 MXN" |

## Loop

```
1. Lead selected (highest risk_score among OPEN leads)
2. Agent chooses a tool from docs/contracts/agent-tools.md, states why
3. Tool executes (read-only), returns result + provenance
4. Agent records an InvestigationStep with a decision:
     FOLLOW    -> go to 2 with a new sub-question
     DISCARD   -> stop this branch; if no branch remains, discard the Lead
     ESCALATE  -> flag for human review, pause this Lead
     CONCLUDE  -> enough evidence exists; hand off to evidence/ for Case assembly
5. Every FOLLOW must add at least one new Evidence record or narrow the
   hypothesis - a step that produces neither is a bug (infinite-loop risk)
```

## Termination guarantees

- **Hop limits** on graph-traversal tools (`max_hops` in
  `docs/contracts/agent-tools.md`) bound how far money-tracing can go per
  call.
- **Step budget per Lead** (implementation detail of `agent/runtime/`,
  document the chosen number once set) — if exceeded, the loop forces
  `ESCALATE`, never silently stops without a recorded reason.
- **No Lead re-opens itself.** A `DISCARDED` Lead stays discarded; a new
  detector run can create a *new* Lead referencing the same entity if new
  signals appear.

## Judge Q&A grounding

`POST /questions` (`docs/contracts/api.md`) answers by retrieving the
relevant `InvestigationStep`/`Evidence`/`Lead` records for the entity in
question and having Gemini narrate over them — never by re-reasoning from
scratch with no citation. See `docs/demo/runbook.md` steps 10-12 for the
exact judge questions this must survive.
