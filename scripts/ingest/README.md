# scripts/ingest/

**Purpose:** defensive parsers turning `data/raw/` (CFDI XML, CSV bank
exports, etc.) into `data/normalized/` records matching `domain/schemas/`.

**What goes here:** one parser per source format. Reject malformed
records rather than best-effort-guessing (`SECURITY.md`).

**Depends on:** `domain/schemas/`, `domain/entities/`.
