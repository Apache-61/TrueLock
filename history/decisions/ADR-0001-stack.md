# ADR-0001: Overall technology stack

**Status:** Accepted
**Date:** 2026-09-12
**Deciders:** bootstrap pass, per team planning context + Research &
Development Operating Pack

## Context

31-hour hackathon, four workstations, "The Forensic Auditor" track. Need a
stack the team already knows (SQL, Python), that supports typed
LLM tool-calling, and that doesn't burn hours on infrastructure that
doesn't move the judging criteria (functioning > precision > traceability
> explanation > demo > sponsor integration > visual design).

## Options considered

| Layer | Options | Chosen | Why not the others |
|---|---|---|---|
| Database | PostgreSQL / MongoDB / Snowflake | **PostgreSQL** | Invoices/payments are relational+temporal; team knows SQL; Mongo/Snowflake add a second data store and a learning curve for no concrete need |
| Graph | NetworkX / graph DB (Neo4j etc.) | **NetworkX** | In-process, fast enough for hackathon data volume, no extra service to deploy; a graph DB is unneeded until proven otherwise |
| LLM | Gemini / local model / multi-model router | **Gemini 2.5** (Flash for cheap steps, Pro for synthesis) | Best documented function-calling + structured-output fit; team has 4 funded Gemini projects |
| Agent orchestration | Custom bounded loop / LangGraph / multi-agent swarm | **Custom bounded loop** | Lower setup cost; LangGraph is optional and revisited only if state management becomes unmanageable; a swarm is unnecessary complexity for one investigator role |
| RAG | Full vector store / local retrieval | **Local retrieval only** | Regulatory corpus (69-B, CFDI 4.0) is small; a vector DB is infra cost without a real retrieval-quality need at this scale |
| Frontend | Next.js+TS / other | **Next.js + TypeScript** | Team familiarity, fast to stand up a shell against a mocked API |
| Graph UI | Cytoscape.js / other | **Cytoscape.js** | Purpose-built for entity/relationship graphs |

## Decision

Next.js/TypeScript frontend, FastAPI/Python backend, PostgreSQL, NetworkX
for graph analysis, Cytoscape.js for graph UI, Gemini via function calling
for the investigation/narrative layer, a custom bounded agent loop (no
framework), and local-only RAG. Full detail: `ARCHITECTURE.md` §3,
`research/infrastructure/README.md`.

## Consequences

Fast to start, minimal new infrastructure to learn under time pressure. If
data volume or agent state complexity outgrows this (see PROJECT_STATE.md
→ "Open decisions"), the two most likely escalations are a graph DB and
LangGraph — both are explicitly deferred, not ruled out.

## Reversibility

High for graph/agent-framework choices (isolated behind
`detection/graph/` and `agent/runtime/` respectively). Lower for the
database once real data is loaded — a migration would be needed, not just
a swap.
