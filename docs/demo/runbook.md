# Demo runbook

The target three-minute judge flow. Nothing in `docs/architecture.md`'s
critical path is done until this runbook can actually be performed.

## Steps

1. **Load a dataset** — a known scenario from `data/synthetic/`
   (`scripts/demo/load_scenario.py`, once implemented).
2. **A lead appears** — the dashboard shows a new `Lead` with its
   `risk_score` and triggering signals.
3. **"I am investigating this because…"** — the UI shows the Lead's
   `reason` and backing `detector_signal`s before any tool call happens.
4. **Agent calls tools**, visibly: supplier lookup, invoice lookup,
   payment lookup, money trace, graph traversal, 69-B check
   (`docs/contracts/agent-tools.md`).
5. **Graph appears** — entities/relationships, highlighted suspicious
   path (Cytoscape.js, `research/graph/README.md`).
6. **Money trail appears** — Invoice → Payment → Account → Transaction →
   Account → Entity (`docs/contracts/domain.md`).
7. **Evidence accumulates** — each `Evidence` card shows source, record,
   claim, and why it's relevant (`docs/contracts/evidence.md`).
8. **One alternative lead is discarded**, on screen, with its
   `discard_reason` — this is a required beat, not optional polish; it's
   half of what makes the system look like an investigator rather than a
   filter.
9. **Case file appears** — hypothesis, amount, entities, evidence,
   discarded leads, limitations, conclusion
   (`docs/contracts/case.md`).
10. **Judge asks: "Why did you investigate Supplier X?"** — answered from
    retrievable `InvestigationStep`s, not free-standing prose
    (`docs/investigation/protocol.md` → "Judge Q&A grounding").
11. **Judge asks: "How much money is involved?"** — answered by
    recomputing from source records, not by repeating a cached number.
12. **Judge asks: "What would change your conclusion?"** — answered from
    `case.limitations`.

## The hidden-fraud moment

Judges must be able to inject or hide a new fraud pattern and watch the
agent find it, without the team having hand-tuned for that specific
pattern. `POST /demo/inject-fraud` (`docs/contracts/api.md`) exists for
this. The injected scenario's answer key
(`data/answer_keys/`) is never exposed to the agent or the frontend —
only used afterward, by the team, to check the result.

## Failure handling

Every primary dependency has a documented fallback
(`research/infrastructure/README.md` → "Fallback matrix"). If Gemini is
unreachable mid-demo, the system falls back to a recorded deterministic
investigation script rather than stopping
(`docs/architecture.md` §12 — "the judge should never see
'Gemini is down, therefore the demo is over.'"). Test this fallback before
the actual demo, not during it.

## Pre-demo checklist

- [ ] Hidden fraud scenario prepared, answer key stored outside the agent's
      reach
- [ ] Money-flow visualization renders correctly on the demo dataset
- [ ] Evidence chain renders end to end
- [ ] At least one discarded lead is visible in the demo scenario
- [ ] At least one insufficient-evidence case exists to show, so the
      system's "reject an accusation" capability is demonstrated too
- [ ] Q&A tested against the three questions above
- [ ] Gemini local fallback tested (kill network, confirm demo survives)
- [ ] Provider/API failover tested (`config/agent-providers.yaml`)
- [ ] Budget monitoring checked, not just assumed
- [ ] Demo environment clean (no leftover test data from a previous run)
