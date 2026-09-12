# Rejected ideas (research phase)

What was evaluated before the build started and deliberately not chosen or
not built now, inherited from the initial planning pack. For rejections
made later, during actual development, see `history/rejected-ideas/README.md`.

## Datasets ignored

- **IEEE-CIS** — large, e-commerce-fraud-oriented, not aligned to the
  invoice/supplier/payment forensic problem. See `research/fraud/README.md`.

## Stack options not chosen

See `history/decisions/ADR-0001-stack.md` for the full comparison. Not
chosen: MongoDB, Snowflake, a dedicated graph database, fine-tuning, GNN/
graph-ML, a full multi-agent swarm framework, LangGraph (deferred, not
ruled out), n8n as core orchestration (useful only as external glue).

## Hard "no touch" for this build

- Custom graph database
- Fine-tuning
- Graph neural networks
- Full multi-agent swarm
- Blockchain-first data architecture
- A second/third database without a concrete necessity
- An elaborate RAG stack (vector DB, chunking pipeline, reranking)
- Voice-first UX

Each of these is a real technique with real hackathons where it's the
right call — just not one where the judging criteria are functioning,
precision, traceability, explanation, demo, sponsor integration, visual
design, in that order, under a 31-hour clock.

## Only if time remains (not "no touch," just not first)

- Solana notarization (`history/decisions/ADR-0004-sponsor-tech-scope.md`)
- ElevenLabs voice
- Polished animations
- Advanced ML anomaly models (beyond the deterministic detector library)
- An external observability platform (Langfuse) beyond a local JSONL log
- Secondary model providers beyond the pooled Gemini projects

## Why write this down

So that, at hour 20, nobody re-opens "should we use a graph database" or
"should we fine-tune something" as if it were a fresh question. It was
asked and answered; re-asking it costs time the team doesn't have. If new
evidence genuinely changes the calculus, that's a new decision — record it
in `history/decisions/`, don't silently override this file.
