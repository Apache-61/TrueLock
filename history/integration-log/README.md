# Integration log

**Purpose:** record every point where two modules (or a module and a
sponsor API) were connected for the first time, or where their contract
changed — the moments most likely to break silently when someone else
touches either side later.

**What goes here:** `YYYY-MM-DD-module-a-x-module-b.md` — what contract
was used (link `docs/contracts/...`), what was tested, what mocks were
replaced, any deviation from the documented contract and why.

**What does not go here:** every PR (only ones that cross a module
boundary or wire in an external service for the first time).

**Depends on:** `docs/contracts/`.
