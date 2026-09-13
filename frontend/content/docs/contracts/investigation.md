# Contract: Investigation step (agent decisions)

Schema: `backend/src/truelock/domain/schemas/investigation_step.schema.json`. This is the
**structured-output contract** referenced in `docs/architecture.md` — every
decision the agent makes is one of these records, never free natural
-language that something downstream has to parse.

## Example

```json
{
  "step_id": "I-007",
  "lead_id": "L-001",
  "action": "TRACE_OUTGOING_FUNDS",
  "tool": "trace_outgoing_funds",
  "reason": "Determine destination of supplier payment",
  "inputs": { "account_id": "012180000000000001", "max_depth": 3 },
  "result_refs": ["TX-ROOT-001", "TX-HOP-001", "HASH:a1b2c3d4e5f6...64hex"],
  "decision": "FOLLOW"
}
```

`result_refs` must include recoverable domain record IDs (transaction,
invoice, RFC, etc.) plus the full SHA-256 execution hash (`HASH:` + 64
hex chars) of the stable tool envelope (excluding `execution_time`).
Hashes alone are not sufficient evidence.

`inputs` must be the **normalized** argument object after alias coercion
and schema validation.

## Decision values

- `FOLLOW` — keep investigating this branch. Allowed only when the step
  added new `source_ids` / Evidence or narrowed the hypothesis.
- `DISCARD` — stop; insufficient signal (e.g. empty money trail).
- `ESCALATE` — flag for human review: ambiguous evidence, invalid or
  repeated tool call/result, tool error, step budget exhausted, or time
  budget exhausted. Always records a recoverable reason.
- `CONCLUDE` — enough evidence exists to assemble the Case
  (`docs/contracts/case.md`). Never used as a silent timeout.

## Rule: the frontend never parses prose to decide what happened

The UI timeline (`docs/demo/runbook.md` step 4, "Observability" in
`docs/architecture.md`) renders these structured steps directly. Any narrative
text the model produces is a *label* on a step, not the mechanism that
drives control flow.

## Investigation protocol (state machine)

See `docs/investigation/protocol.md` for the full bounded-loop design:
how a Lead becomes a sequence of Investigation Steps, when the loop
terminates, and how a discarded branch is recorded.

## Ownership

Owned by the Forensic Investigator subsystem (`backend/src/truelock/agent/investigator.py`).
