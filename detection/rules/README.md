# detection/rules/

**Purpose:** one file per detector, implementing `docs/contracts/detector.md`
against the patterns in `docs/detection/rules.md`.

**What goes here:** pure functions named after their `detector_id` (e.g.
`duplicate_invoice.py` implementing `DUPLICATE_INVOICE`), plus
`__init__.py` acting as the detector registry.

**What does not go here:** scoring/thresholding (→ `detection/scoring/`),
graph algorithms shared across detectors (→ `detection/graph/`, imported
from here, not duplicated).

**Depends on:** `domain/entities/`, `docs/detection/rules.md`.
