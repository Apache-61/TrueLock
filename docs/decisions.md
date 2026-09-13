# Architectural & Forensic Decisions

A consolidated record of active product decisions for TrueLock.

---

## ADR-0001: Technical Stack
- **Backend**: Python 3.10+ with FastAPI for REST API, Pydantic v2 for strict domain validation.
- **Frontend**: Next.js 14 with React and TypeScript.
- **Database**: PostgreSQL 15 for relational transaction and ledger storage; in-memory repository protocol for rapid local development and isolated test suites.
- **LLM**: Server-side Google Gemini API (`gemini-2.5-flash`) utilizing typed function calling for bounded tool selection.

---

## ADR-0002: Deterministic Authority vs. Generative Reasoning
- **Context**: LLMs hallucinate calculations, fail to guarantee mathematical precision, and cannot be trusted with raw financial sums.
- **Decision**: All financial arithmetic, graph traversals, detector executions, and finding admissibility checks are implemented deterministically in Python. Gemini is restricted to hypothesis formulation, tool selection from a strict allowlist, and grounded Q&A.

---

## ADR-0003: Single Import Root (`backend/src/truelock/`)
- **Context**: The initial codebase was fragmented across root-level folders (`domain/`, `detection/`, `agent/`, `evidence/`, `backend/`, `scripts/`), causing circular dependencies and confusing imports.
- **Decision**: Consolidate all product code under `backend/src/truelock/`. Keep `database/` for operational SQL assets only.

---

## ADR-0004: Evidence & Exposure Accounting Invariants
- **Context**: Summing transaction hops in cyclical money laundering schemes artificially inflates exposure figures.
- **Decision**: Exposure is anchored to unique root disbursements. Downstream hops and circular returns are tracked separately and deducted to calculate true net exposure.
