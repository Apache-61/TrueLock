# ADR-0002: Determinism / AI split for forensic reasoning

**Status:** Accepted
**Date:** 2026-09-12
**Deciders:** bootstrap pass, per team planning context + Research &
Development Operating Pack §6, §57

## Context

The challenge explicitly penalizes a system that presents suspicion as
fact. An LLM-only pipeline risks hallucinated relationships, invented
amounts, or an EFOS listing silently treated as proof of fraud. The system
must be able to say why it investigated something and what evidence
supports or fails to support a conclusion, on demand, in front of judges.

## Decision

Split the system into two kinds of intelligence that never trade places:

```
FORENSIC INTELLIGENCE  = investigator operating on financial evidence
DEVELOPMENT INTELLIGENCE = AI workers building this repository
```

Within forensic intelligence, further split by function:

- **Deterministic** (rules, arithmetic, graph traversal, EFOS status
  lookup, database integrity, evidence identity/provenance): signal
  detection, risk scoring, money-flow tracing, final amount computation.
- **Gemini via function calling** (never raw SQL access): interpreting
  which lead to investigate next, choosing which tool to call, synthesizing
  evidence into a narrative, deciding whether a hypothesis remains worth
  pursuing, generating the case narrative, answering auditor questions.

All agent decisions return a strict JSON schema (`docs/contracts/
investigation.md`); no natural-language parsing drives control flow.

## Consequences

Every conclusion is traceable to a deterministic computation or a
retrievable tool-call result, never to "the model inferred it." This is
slower to build than a pure prompt-and-hope pipeline but is the actual
product differentiator per the challenge brief (§7/§8 of the original
planning context — "the system must not present suspicion as fact").

## Reversibility

High for which specific tasks are delegated to the LLM (the boundary is a
policy list in `agent/policies/`, not a structural constraint). Low for the
principle itself — reversing it would mean re-deriving the entire
evidence-chain trust story right before a demo, which is not a risk worth
taking under time pressure.
