# scripts/validate/

**Purpose:** standalone validation runnable from CI or by hand — JSON
Schema validity checks, task-queue file well-formedness, fixture/schema
consistency.

**What goes here:** scripts that `tests/contract/` also exercises via
pytest; kept runnable standalone (`python scripts/validate/schemas.py`)
so a contributor can check quickly without running the whole suite.

**Depends on:** `domain/schemas/`.
