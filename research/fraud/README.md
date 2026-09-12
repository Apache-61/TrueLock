# Fraud / AML dataset & simulator research

Evaluates the datasets and simulators available for generating test
scenarios. The actual fraud-pattern library (what we detect, and how) is
documented separately in `docs/detection/rules.md` — this file is about
where **test data** comes from.

## IBM AMLSim — USE (as scenario generator, not production data)

Repository: https://github.com/IBM/AMLSim

Synthetic transaction simulator generating banking transactions and known
money-laundering patterns for graph/ML experimentation: fan-in, fan-out,
cycle, bipartite, stack, random, scatter-gather, gather-scatter.

**Decision:** use as a **test/scenario generator** only:

```
AMLSim → scenario generation → normalized fixture → detector → lead →
investigation → expected result
```

This gives repeatable ground truth for regression tests
(`tests/scenarios/`).

## Fraud Detection Handbook — USE (secondary test data)

- Repo: https://github.com/Fraud-Detection-Handbook/fraud-detection-handbook
- Simulation docs: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html

Useful for synthetic fraud, temporal features, imbalanced classification,
regression scenarios. Secondary — not the primary Mexican-domain
representation (that's the SAT/CFDI-grounded synthetic dataset the team
builds itself, see `data/synthetic/README.md`).

## PaySim — P1 benchmark / inspiration

Synthetic financial transactions with type/amount/origin/destination/
balance/fraud-flag fields. Not core; useful only if a P1 benchmark is
wanted after the core loop works.

## IEEE-CIS — IGNORE for hackathon core

Large, e-commerce-fraud-oriented, not aligned to the invoice/supplier/
payment forensic problem. Explicitly out of scope — see
`research/rejected-ideas/README.md`.

## AMLNet — P1 fallback benchmark

Synthetic AML transaction graph dataset: https://zenodo.org/records/16482144.
Only relevant if AMLSim setup fails and a fallback graph dataset is needed.

## Priority order

### P0
1. SAT 69-B / EFOS snapshot
2. Challenge-provided datasets (once the official PDF/materials are
   available — see `docs/challenge/README.md`)
3. IBM AMLSim generated scenarios
4. Fraud Detection Handbook simulator output
5. Small synthetic invoice/payment/supplier dataset designed by the team
   (`data/synthetic/`)

### P1
6. PaySim
7. AMLNet
8. Elliptic (https://www.elliptic.co/newsroom/elliptic-releases-bitcoin-transactions-data/)

### Ignore for the core
9. IEEE-CIS
