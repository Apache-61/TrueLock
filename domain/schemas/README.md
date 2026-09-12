# domain/schemas/

**Purpose:** the frozen JSON Schema contracts — the single source of truth
for every shared data shape in TrueLock. See `docs/contracts/` for the
prose explanation of each, and `domain/README.md` for the full file list.

**What goes here:** `*.schema.json` files, draft-07, one type per file,
validated by `tests/contract/test_schemas.py`.

**What does not go here:** implementations (`domain/entities/`), example
data (`data/fixtures/`), anything not meant to be a cross-module contract.

**Changing a file here requires human authorization** — every other
module (`database/`, `detection/`, `agent/`, `backend/`, `frontend/`)
treats these as frozen. If a change is genuinely needed, open a
`type:decision` issue first.

**Depends on:** `research/sat/README.md` for the regulatory fields.
