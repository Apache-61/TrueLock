# Dataset strategy

See `research/fraud/README.md` for per-dataset evaluation. This file is
the operational checklist: what to have cached locally before the main
build starts, so the demo never depends on a live network call to a
third-party site.

## Offline caching checklist (P0 unless noted)

- [ ] Official challenge PDF — scoring and exact requirements
- [ ] SAT 69-B / EFOS data snapshot — local fiscal evidence
      (`data/raw/sat-69b-snapshot/`, gitignored — do not commit raw
      government data dumps directly; commit a small derived fixture
      instead, see `data/fixtures/README.md`)
- [ ] CFF current text — regulatory context
- [ ] SAT Anexo 20 / CFDI docs — schema and semantics
- [ ] Payment complement documentation — payment linkage
- [ ] AMLSim repo + examples — test scenarios
- [ ] Fraud Detection Handbook simulator — regression data
- [ ] Gemini SDK docs — API stability
- [ ] Graph/UI library docs (P1) — avoid internet dependency mid-demo
- [ ] Agent framework docs (P1) — only if LangGraph ends up used

## Where cached/derived data lives

- `data/raw/` — raw pulls (gitignored, never committed wholesale)
- `data/normalized/` — canonicalized records matching `domain/schemas/`
- `data/fixtures/` — small, committed, hand-curated or derived fixtures
  used by tests and the demo
- `data/synthetic/` — generated scenarios (AMLSim-style + hand-built rings)
- `data/answer_keys/` — expected detector/investigation output per
  scenario, kept out of the agent's reach (see `data/answer_keys/README.md`)
