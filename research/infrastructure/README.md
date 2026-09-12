# Infrastructure research

Full stack, services, and fallback research backing `ARCHITECTURE.md` §3.
See `history/decisions/ADR-0001-stack.md` for the decision itself; this is
the supporting detail.

## Provisional stack (full table)

| Layer | Candidate | Status |
|---|---|---|
| Frontend | Next.js + TypeScript | GO |
| Backend | FastAPI + Python | GO |
| Domain contracts | JSON Schema (+ Pydantic at implementation) | GO |
| Database | PostgreSQL | GO |
| Graph analysis | NetworkX | GO |
| Graph visualization | Cytoscape.js | GO |
| LLM | Gemini 2.5 Flash / current stable low-latency equivalent | GO |
| Tool calling | Gemini function calling | GO |
| Structured output | JSON schema / typed responses | GO |
| RAG | local/document retrieval first | GO, limited |
| Agent orchestration | bounded custom loop | GO |
| Agent framework | LangGraph | OPTIONAL |
| Observability | local event log first, Langfuse optional | GO |
| AML simulation | IBM AMLSim | USE for test generation |
| Fraud simulator | Fraud Detection Handbook | USE for test generation |
| MongoDB | — | NO initially |
| Snowflake | — | NO initially |
| Graph DB | — | NO initially |
| Fine-tuning | — | NO |
| GNN / Graph ML | — | NO initially |
| Solana | evidence notarization only | OPTIONAL |
| ElevenLabs | accessibility / presentation | OPTIONAL |
| Local LLM | fallback | OPTIONAL |

## APIs and services

| Service | Use | Primary API | Fallback | Priority |
|---|---|---|---|---|
| Gemini | reasoning + tool selection | Gemini API | recorded fixtures / local model | P0 |
| SAT datasets/docs | fiscal evidence | web/download | cached snapshot | P0 |
| PostgreSQL | canonical persistence | SQL | SQLite | P0 |
| GitHub | source/control/coordination | REST/Git | local Git | P0 |
| Langfuse | optional traces | SDK/API | local JSON event log | P1 |
| ElevenLabs | optional voice | REST | browser/system TTS | P2 |
| Solana | optional notarization | RPC | local hash manifest | P2 |

## Fallback matrix (what breaks the demo if X is down)

| Primary | Fallback |
|---|---|
| Gemini | recorded fixture / deterministic agent script |
| Gemini project A | authorized project B (see `orchestrator/policies/provider-pool.yaml`) |
| PostgreSQL | SQLite |
| SAT online | cached snapshot |
| NetworkX | direct adjacency traversal |
| Cytoscape | table/path view |
| Langfuse | JSONL event log |
| ElevenLabs | text-only / browser TTS |
| Solana | local hash manifest |
| Cloud host | local/server fallback |
| External dataset | synthetic fixture |

The judge should never see "Gemini is down, therefore the demo is over" —
every primary has a deterministic fallback path. See
`docs/demo/runbook.md` §Failure handling.

## Sponsor integration order

1. Gemini — core functionality
2. TigerData/PostgreSQL — data substrate
3. Best .Tech — public demo hosting
4. Solana — optional evidence notarization (hash → notarize, never every
   transaction on-chain)
5. ElevenLabs — final presentation/accessibility layer

Snowflake and MongoDB: only if a concrete, compelling need emerges — see
`research/rejected-ideas/README.md`.
