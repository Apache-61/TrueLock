# AI / LLM strategy research

## Model choice

**Gemini 2.5 Flash** (or current stable low-latency equivalent) for most
agent steps; **Gemini 2.5 Pro** for final synthesis/Q&A where reasoning
quality matters more than latency. FACT/OFFICIAL: Google documents
function calling and structured output for Gemini.

- Function calling: https://ai.google.dev/gemini-api/docs/function-calling
- Structured output: https://ai.google.dev/gemini-api/docs/structured-output
- GenerateContent / usage metadata: https://ai.google.dev/api/generate-content

## What the model decides vs. never decides

See `ARCHITECTURE.md` §2 and §6, and `history/decisions/ADR-0002-determinism-ai-split.md`
for the accepted split. Summary:

**Model decides:** which lead to investigate, which tool to call next,
whether a hypothesis remains worth pursuing, evidence synthesis, case
narrative, answering auditor questions.

**Model never decides:** raw financial arithmetic, EFOS status
computation, database integrity, final amount computation, source
provenance, evidence identity.

## Structured output contract

Every agent decision returns a fixed schema, e.g.:

```json
{
  "decision": "FOLLOW",
  "reason": "Payment destination has an unexplained related-party relationship",
  "next_action": "TRACE_OUTGOING_FUNDS",
  "required_input": { "transaction_id": "TX-0042" }
}
```

The frontend never parses natural language to decide what happens next —
see `docs/contracts/investigation.md`.

## Token/cost governance

Gemini responses expose usage metadata (prompt tokens, cached tokens,
candidate tokens, tool-use prompt tokens, thoughts tokens, total tokens).
Record per request in a usage ledger (`orchestrator/policies/usage-ledger.schema.json`):

```
provider, project, model, request_id, timestamp, input_tokens,
output_tokens, cached_tokens, estimated_cost, status, error
```

Sources:
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/caching
- https://ai.google.dev/gemini-api/docs/rate-limits

## Model-tier routing (cost control)

Don't use the strongest model for every task — classify tasks and route to
the cheapest capability that satisfies them (applies to *development*
workers too, not just the forensic agent):

```
TIER 0 — deterministic:   formatting, tests, schema validation, grep/search, dataset transforms
TIER 1 — cheap reasoning: summarize, classify, inspect logs, propose a simple patch
TIER 2 — strong reasoning: architecture, hard debugging, evidence synthesis, ambiguous investigation
TIER 3 — human-required:  architecture changes, security-sensitive changes, irreversible deploys
```

## High-value cost controls

Short prompts; structured context; local retrieval before calling the
model; deterministic filtering before the LLM sees anything; context
caching where reused; low-cost model for simple work; strong model only
for genuine ambiguity; record token usage; budget alerts; hard stop
thresholds. See `orchestrator/policies/provider-pool.yaml`.

## RAG scope

Local/document retrieval only — the regulatory corpus (69-B, CFDI 4.0) is
small enough that a full vector-store stack is not worth the setup time.
See `docs/regulatory/` for the corpus itself.
