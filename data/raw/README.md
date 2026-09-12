# data/raw/

**Purpose:** unmodified pulls from external sources (SAT snapshots, AMLSim
output, any challenge-provided dataset).

**Gitignored** — everything except this README. Never commit a raw
government or financial data dump wholesale; derive a small fixture into
`data/fixtures/` instead.

**What goes here:** raw downloads, exactly as fetched.

**Depends on:** `research/datasets/README.md` §Offline caching checklist.
