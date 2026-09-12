# Contract: Investigation step (agent decisions)

Schema: `domain/schemas/investigation_step.schema.json`. This is the
**structured-output contract** referenced in `ARCHITECTURE.md` §6 — every
decision the agent makes is one of these records, never free natural
-language that something downstream has to parse.

## Example

```json
{
  "step_id": "I-007",
  "lead_id": "L-001",
  "action": "TRACE_OUTGOING_FUNDS",
  "tool": "trace_transactions",
  "reason": "Determine destination of supplier payment",
  "inputs": { "transaction_id": "TX-8841" },
  "result_refs": ["TX-9011", "TX-9014"],
  "decision": "FOLLOW"
}
```

## Decision values

- `FOLLOW` — keep investigating this branch.
- `DISCARD` — stop; insufficient signal to continue (record why in the
  Lead's `discard_reason` if this ends the lead entirely).
- `ESCALATE` — flag for human review (e.g. ambiguous evidence that a
  human auditor should see before the case commits to a status).
- `CONCLUDE` — enough evidence exists to assemble the Case
  (`docs/contracts/case.md`).

## Rule: the frontend never parses prose to decide what happened

The UI timeline (`docs/demo/runbook.md` step 4, "Observability" in
`ARCHITECTURE.md`) renders these structured steps directly. Any narrative
text the model produces is a *label* on a step, not the mechanism that
drives control flow.

## Investigation protocol (state machine)

See `docs/investigation/protocol.md` for the full bounded-loop design:
how a Lead becomes a sequence of Investigation Steps, when the loop
terminates, and how a discarded branch is recorded.

## Who owns this contract

Agent D (Agent/Evidence).
