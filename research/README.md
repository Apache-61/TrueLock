# Research

Source material and reasoning that backs the decisions in `ARCHITECTURE.md`
and `DECISIONS.md`. This is where "why did we think this was true" lives,
distinct from "what did we decide" (`history/decisions/`).

- `sat/` — SAT / Article 69-B / CFDI 4.0 / payment-complement regulatory
  research.
- `fraud/` — evaluation of fraud/AML datasets and simulators (AMLSim,
  Fraud Detection Handbook, PaySim, IEEE-CIS, AMLNet, Elliptic).
- `datasets/` — dataset priority ordering and offline-caching checklist.
- `ai/` — Gemini/LLM strategy, cost governance, model-tier routing.
- `graph/` — graph-analysis and graph-visualization research.
- `infrastructure/` — full stack/API/services research and the fallback
  matrix behind `ARCHITECTURE.md` §3.
- `rejected-ideas/` — what we evaluated and did **not** build, and why,
  from the initial research phase (see `history/rejected-ideas/` for
  rejections made later, during actual development).

## Source status convention

Every claim in this tree should be tagged as one of:

- **FACT / OFFICIAL** — directly supported by primary documentation (cite
  the URL).
- **INFERENCE** — an engineering conclusion derived from available
  evidence, not stated outright by a primary source.
- **RECOMMENDATION** — what the team should do, given the above.
- **HYPOTHESIS** — untested, to be validated experimentally (see
  `history/experiments/README.md`).

Do not present a regulatory or scoring claim as FACT unless it traces to
an official source (SAT, DOF, the challenge PDF, or documented vendor API
behavior).
