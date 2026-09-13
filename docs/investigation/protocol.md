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

## Loop (Fase 2)

```
1. Lead selected
2. Select next action (deterministic plan; Gemini may propose an override)
3. Validate args against docs/contracts/agent-tools.md
   - invalid Gemini args → keep deterministic plan and record audit note
   - invalid final args → ESCALATE (never execute)
4. Execute tool (read-only) via ToolRegistry → envelope + provenance
5. Reduce: update context, materialize Evidence, store full result hash
6. Decide:
     FOLLOW    -> go to 2 only if new sources/evidence OR narrowed hypothesis
     DISCARD   -> empty trail / no remaining productive branch
     ESCALATE  -> repeated call, repeated result hash, tool error,
                  step budget, or time budget
     CONCLUDE  -> enough evidence; hand off to case assembly
```

Gemini and the offline fallback share steps 3–6. The fallback never emits
a partial `function_call`; it selects the deterministic plan and runs it
through the same validator and dispatcher.

## Progress rule

Every `FOLLOW` must add at least one new Evidence record / `source_id` or
narrow the hypothesis. A step that produces neither is a protocol bug and
must terminate with `ESCALATE`.

## Termination guarantees

- **Hop limits** on graph-traversal tools (`max_depth`, default 3, cap 5)
  bound how far money-tracing can go per call.
- **Step budget** (`MAX_INVESTIGATION_STEPS`, default 10) — if exceeded,
  the loop forces `ESCALATE` via `step_budget_guard` with a recorded reason.
- **Time budget** (`MAX_INVESTIGATION_SECONDS`, default 30) — if exceeded,
  the loop forces `ESCALATE` via `time_budget_guard` with elapsed time.
- **No Lead re-opens itself.** A `DISCARDED` Lead stays discarded; a new
  detector run can create a *new* Lead referencing the same entity if new
  signals appear.

## Judge Q&A grounding

`POST /questions` (`docs/contracts/api.md`) answers by retrieving the
relevant `InvestigationStep`/`Evidence`/`Lead` records for the entity in
question and having Gemini narrate over them — never by re-reasoning from
scratch with no citation. See `docs/demo/runbook.md` steps 10-12 for the
exact judge questions this must survive.
