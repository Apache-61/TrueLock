# data/

**Purpose:** every dataset the system uses, split by how trustworthy/
committed it is. See `research/datasets/README.md` for the sourcing
strategy behind this.

- `raw/` — unmodified pulls from external sources. **Gitignored** — never
  commit raw government/financial data dumps wholesale.
- `normalized/` — canonicalized records matching `domain/schemas/`,
  produced by `scripts/ingest/`.
- `fixtures/` — small, committed, hand-curated or derived datasets used by
  tests and local dev.
- `synthetic/` — generated fraud scenarios (AMLSim-style + hand-built
  rings) with known ground truth.
- `answer_keys/` — expected detector/investigation/case output per
  scenario. Kept conceptually and physically separate from `synthetic/`
  so the agent/frontend never has an accidental path to them.
