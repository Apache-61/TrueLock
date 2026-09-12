# TrueLock — Architecture

This is the frozen-for-now set of architectural decisions for the hackathon
build. It answers the open questions from the initial planning context by
committing to concrete choices, each checked against: is it necessary, does
it fit in 31 hours, do we have the skills/docs for it, does it move the
judging criteria. Full reasoning and sourcing for each choice lives in
`research/` and `history/decisions/`; this file is the summary a new
contributor (human or AI) should read first.

## 1. Core thesis

TrueLock is not an anomaly classifier with an LLM bolted on. It is a
**forensic investigation system**:

```
DATA → NORMALIZATION → DETERMINISTIC SIGNALS → LEADS → INVESTIGATION TOOLS
→ AI INVESTIGATOR → EVIDENCE CHAIN → CASE / CONCLUSION → AUDITOR Q&A
```

and it must always keep these categories distinct, never collapsing one
into another:

```
observed fact ≠ anomaly ≠ hypothesis ≠ lead ≠ evidence ≠ inference ≠ conclusion
```

The system must be able to answer: why did you investigate this, what did
you find, what did you *not* find, what did you discard and why, and why is
the final conclusion supported or unsupported. See
`docs/investigation/protocol.md`.

## 2. Determinism / AI split (the key decision)

| Layer | Mechanism | Why |
|---|---|---|
| Signal detection | Deterministic rules (Python) | Must be reproducible and defensible to a human auditor |
| Pursue/discard a lead | Explicit rules + documented thresholds | The reason to discard must be citable, not "the model said so" |
| Relationship / money-flow tracing | Deterministic graph (NetworkX) over canonical data | Exact traceability, not probabilistic |
| Narrative, justification, judge Q&A, synthesis | Gemini via function calling over the tools above | This is where an LLM adds real value: explaining, not deciding facts |

The model never owns: raw financial arithmetic, EFOS status, database
integrity, final amount computation, source provenance, or evidence
identity. Those stay deterministic. See `research/ai/README.md`.

## 3. Provisional stack

| Layer | Choice | Status |
|---|---|---|
| Frontend | Next.js + TypeScript | GO |
| Backend | FastAPI + Python | GO |
| Domain contracts | JSON Schema (+ Pydantic at implementation time) | GO |
| Database | PostgreSQL | GO |
| Graph analysis | NetworkX | GO |
| Graph visualization | Cytoscape.js | GO |
| LLM | Gemini 2.5 Flash (cheap steps) / Pro (synthesis, Q&A) | GO |
| Tool calling | Gemini function calling | GO |
| Structured output | JSON Schema / typed responses | GO |
| RAG | local/document retrieval only, small corpus | GO, limited |
| Agent orchestration | bounded custom loop | GO |
| Agent framework | LangGraph | OPTIONAL, only if the custom loop becomes unmanageable |
| Observability | local JSONL event log first | GO |
| AML simulation | IBM AMLSim | test/scenario generation only |
| Fraud simulator | Fraud Detection Handbook | secondary test data |
| MongoDB / Snowflake / graph DB / fine-tuning / GNN | — | NO for this build |
| Solana | evidence hash notarization only | OPTIONAL |
| ElevenLabs | accessibility / presentation | OPTIONAL |

Full rationale and sources: `research/infrastructure/README.md`.

## 4. Persistence

**PostgreSQL**, no Mongo, no Snowflake, for this build.

- Invoices, payments, providers, accounts are relational, timestamped data —
  a standard SQL use case, and the team already knows SQL.
- The final case file is stored as `JSONB` in the same Postgres instance
  instead of standing up Mongo — one database, one operational surface.
- Snowflake has no volume or analytical need here and no one on the team
  has hands-on experience with it under time pressure.
- `SQLite` is the documented fallback if Postgres setup ever blocks the
  demo (see `docs/architecture` fallback matrix in `research/infrastructure/`).

Schema draft: `database/migrations/0001_init.sql`.

## 5. Graph

NetworkX is enough for the core: traversal, shortest path, connected
components, cycle detection, degree/fan-in/fan-out, time-bounded path
search. A graph database is unnecessary until the dataset or performance
proves otherwise. Visualization: Cytoscape.js in the frontend; fallback is
a plain table/path view if rendering becomes a time sink.

## 6. LLM / agent boundary

Gemini via function calling over a fixed, typed tool surface (see
`docs/contracts/agent-tools.md`) — never unrestricted SQL. All agent
decisions return a strict JSON schema (see `docs/contracts/investigation.md`);
the frontend never parses natural language to decide what happened next.
RAG is deliberately minimal: the regulatory corpus (Art. 69-B/EFOS, CFDI 4.0)
is small enough to pass as static context plus citations embedded in
detector code, rather than standing up a vector store.

## 7. Blockchain (Solana) — bounded, optional

Not on the critical path. If time remains: hash the finalized case file
(SHA-256) and anchor that hash in a Solana devnet memo transaction, purely
for tamper-evidence ("this case file was not altered after date X"). No
fraud-detection logic ever runs on-chain. See `research/rejected-ideas/`.

## 8. Voice (ElevenLabs) — optional, last

Reads the final case conclusion aloud. Wired only after the detection →
investigation → evidence → case loop works end-to-end. Non-core.

## 9. Case file

Single structured JSON (see `docs/contracts/case.md`) rendered to
Markdown/HTML for a human auditor. Required fields: fraud scheme summary,
providers involved, evidence chain, monetary amount, discarded leads (with
reason), confidence level, citations.

## 10. What we do NOT build in this phase

Per the operating pack's time-sink list: no custom graph database, no
fine-tuning, no GNNs, no full multi-agent swarm, no blockchain-first data
architecture, no second/third database without necessity, no elaborate RAG
stack, no voice-first UX. These are documented as explicitly rejected in
`research/rejected-ideas/README.md`, not as pending work.

## 11. Repository as coordination layer

Because four people/AIs build in parallel, this repository itself is
infrastructure: contracts freeze interfaces so modules can be built against
mocks, `tasks/` is the task queue with a claim protocol that prevents two
workers from doing the same task, and `history/` is the engineering memory
so a new contributor can resume without replaying the whole conversation.
See `CONTRIBUTING.md` and `tasks/README.md`.

## 12. Critical path

```
CANONICAL CONTRACTS → SYNTHETIC TEST CASE → DETECTOR → LEAD → TOOL API →
AGENT → EVIDENCE → CASE FILE → API → FRONTEND → DEMO HARDENING
```

Sponsor extras (Solana, ElevenLabs, Snowflake) sit outside this path and
are cut first if time runs short.
