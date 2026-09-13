# Fraud detection library

Every row here is a deterministic detector (`docs/contracts/detector.md`),
never an LLM call. Priority order matches what unlocks a demoable vertical
slice fastest (`docs/architecture.md`).

## High-value deterministic patterns

| Pattern | Detector ID | Inputs | Method | Explainability | Demo value | Priority |
|---|---|---|---|---|---|---|
| Duplicate invoice | `DUPLICATE_INVOICE` | invoice IDs/amount/date/supplier | duplicate keys + fuzzy match | Very high | High | P0 |
| Duplicate payment | `DUPLICATE_PAYMENT` | payment refs/amount/time | exact + near-duplicate | High | High | P0 |
| Unusual amount | `UNUSUAL_AMOUNT` | historical supplier amounts | robust statistics (median/MAD) | High | High | P0 |
| Supplier concentration | `SUPPLIER_CONCENTRATION` | supplier/client history | concentration ratio | High | High | P0 |
| Invoice-payment mismatch | `INVOICE_PAYMENT_MISMATCH` | invoice/payment | reconciliation | Very high | Very high | P0 |
| Rapid pass-through | `RAPID_PASS_THROUGH` | transactions/timestamps | temporal chain (funds in, funds out fast) | High | Very high | P0 |
| Fan-in | `FAN_IN` | account graph | in-degree/amount concentration | High | Very high | P0 |
| Fan-out | `FAN_OUT` | account graph | out-degree/amount dispersion | High | Very high | P0 |
| Cycles | `CIRCULAR_FLOW` | account graph | cycle detection | Very high | Very high | P0 |
| Shell-like entity network | `SHELL_NETWORK` | company/supplier links | shared address/phone/registration-date clustering | Medium | High | P1 |
| 69-B correlation | `69B_CORRELATION` | RFC | SAT status lookup | Very high | Very high | P0 |
| Unusual timing | `UNUSUAL_TIMING` | timestamps | temporal heuristics (e.g. same-day payment) | Medium | High | P1 |

## Scoring

Each detector emits `detector_signal` records
(`domain/schemas/detector_signal.schema.json`). `detection/scoring/`
aggregates signals per entity into a `risk_score` (deterministic weighted
sum — no ML model for this build, see `research/rejected-ideas/README.md`)
and produces a `Lead` when the score crosses a documented threshold
(`docs/contracts/leads.md`). The exact weights are implementation detail
of `TASK-004`; document them in `detection/scoring/README.md` once set, so
they're citable when a judge asks "why this threshold."

## Graph patterns

`FAN_IN`, `FAN_OUT`, and `CIRCULAR_FLOW` run over the money-flow graph
(`research/graph/README.md`) built in `detection/graph/`, using NetworkX.

## Test scenarios

Every pattern above needs at least one fixture in `tests/scenarios/` with
a known answer key in `data/answer_keys/` — see `docs/testing.md`.
