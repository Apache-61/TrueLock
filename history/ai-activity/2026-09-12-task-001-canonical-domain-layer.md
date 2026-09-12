# 2026-09-12 — TASK-001: Canonical domain data ingestion & normalization

- **task_id:** TASK-001 (issue
  [#1](https://github.com/Apache-61/TrueLock/issues/1))
- **worker:** `WORKER-ORCH` — Claude Code session
  (`session_01HCuj7J8sDnxffXHCVsnZeV`), human-directed. Claimed through
  the real protocol (`task_cli.py claim` → `verify` → WON).
- **branch:** `claude/peaceful-noether-5lzmqd` (this session's assigned
  branch, rather than the `feature/TASK-001-…` name the worker would
  generate — noted so the next reader is not confused)
- **start / end:** 2026-09-12
- **result:** DONE — 577 tests passing, ruff clean

## Goal

The head of the critical path: canonical entities mirroring
`domain/schemas/`, ingestion normalizers that produce them, and the
repository read surface every later module goes through.

## What was built

**`domain/entities/`** — the six canonical records (`Entity`, `Provider`,
`Invoice`, `Payment`, `Transaction`, `Account`) as Pydantic models
mirroring their schemas 1:1.

The validation stance is set once in `base.py` and is deliberately
unforgiving: `extra="forbid"`, `frozen=True`, explicit types. **A record
we do not understand is rejected, not repaired.** The failure that
prevents is specific — a forensic conclusion resting on a field that was
silently coerced or defaulted is worse than no conclusion, because it
looks equally confident.

Two normalizations *are* applied, because both lose nothing and skipping
either breaks joins silently: RFCs are upper-cased (otherwise one
supplier becomes two, defeating every concentration and duplicate rule),
and a CFDI `Fecha` datetime is truncated to the contract's `date`.

One cross-field rule went in here rather than into a detector: a provider
carrying an `efos_listed_date` with a non-listed `efos_status` is
refused. A record that says both "never listed" and "listed on this date"
cannot be reasoned about, and whichever half a later rule happens to
read, the other half silently becomes a lie.

**`scripts/ingest/`** — CFDI 4.0 XML and bank-CSV normalizers. Every
rejection carries a source, a locator and a reason, and `IngestResult.ok`
is true only when nothing was refused, so a caller that tolerates
rejections has to look at them. The distinction that matters:
a `Rejection` means *this record* is unusable, keep going (one corrupt
file must not fail a directory of thousands); an `IngestError` means the
*source* is unusable, stop (a CSV missing its amount column is a mapping
error, and ingesting a partial table would hide it).

**`backend/repositories/`** — the read surface as `Protocol`s that import
no database driver, plus in-memory implementations. That boundary is
TASK-001's fourth acceptance criterion and it is what lets TASK-005,
TASK-019 and TASK-032 be built and tested *before* the database exists,
the same way the frontend shell is built against its mock. The in-memory
implementation is not a toy — it is the fixture every downstream task
develops against, so query semantics (ordering, endpoint inclusivity,
absence as a normal answer, refusal of negative paging) are pinned there
once rather than re-decided per module.

## Tests

577 passing (from 446), ruff clean.

- `tests/contract/test_entity_schema_alignment.py` (43) — every entity
  against its schema field by field: properties both directions,
  required/optional, enum values, defaults, extra-property policy. This
  catches quiet drift: if a schema gains a field and the entity does not,
  `extra="forbid"` raises *nothing* — it only rejects fields the model
  does not know — so records just arrive missing data and a detector
  later reports "no signal" instead of "I could not see that column".
- `tests/unit/test_domain_entities.py` (39) — round-trip identity,
  and a rejection test per malformed shape, each naming the wrong answer
  it prevents.
- `tests/unit/test_ingest.py` (19) — accepted and rejected paths for both
  parsers, including that a bad file is one rejection rather than a crash.
- `tests/unit/test_repositories.py` (29) — query semantics, plus a test
  that parses `interfaces.py`'s imports to assert the no-driver boundary
  holds, rather than asserting it in prose.

## Two backlog defects found by doing the work

Both would have cost every machine, so they are fixed in the backlog and
re-seeded rather than just worked around here:

1. **No task declared `tests/` in its `allowed_paths`.** Every task's
   "Tests required" section names files under `tests/`, but the scope
   guard would have refused them — so every task, on every machine, would
   have stopped BLOCKED for a scope violation it was explicitly
   instructed to commit. `TaskDefinition.test_paths` now renders into
   every task's allowed paths, and the concurrency-collision check
   deliberately ignores test paths (each task writes its own named file;
   a clash there is a rename, not a lost change).
2. **`task_cli.py` sent no `Content-Type` header**, so every write
   returned HTTP 415. The manual claim path — the one `tasks/README.md`
   tells a human to use — was unusable, while the worker's own client
   (which does send it) worked fine, so the breakage only showed up for a
   human.

## Scope

My diff was checked against TASK-001's own `ScopeGuard` and passes.

TASK-001's `allowed_paths` were extended by one thing: `requirements.txt`
and `requirements-dev.txt`. The task asks for Pydantic models
(ARCHITECTURE.md: "JSON Schema (+ Pydantic at implementation time)") and
a task cannot deliver those without declaring the dependency — CI
installs `requirements-dev.txt`, so without it the suite would fail on
import. Pydantic is pinned, because a validation library that changes its
strictness between minor versions changes what this system accepts as a
valid record.

## Known issues / for the next worker

- **`Payment.transaction_ids` is a tuple, not a relation.** Fine for
  in-memory use; TASK-009 should decide whether it becomes a join table
  when it lands the SQL repositories.
- **No `conceptos[]` structure on `Invoice`.** The schema keeps a
  free-text `concept` summary and says to preserve the structured
  line items "once ingestion is implemented". It is not implemented —
  line-item-level duplicate detection would need it, so TASK-013 or
  TASK-014 may need to extend the contract (which needs sign-off,
  `CONTRIBUTING.md` §5).
- **CFDI parsing is a reader for the canonical subset, not a validator.**
  Anexo 20 XSD validation is a separate concern
  (`docs/regulatory/cfdi-40.md`).
- **Only one bank CSV layout is proven** — the default mapping plus one
  alternative in tests. Real exports will need their own `BankCsvMapping`.
- **No `Provider` ingestion parser yet.** Providers currently come from
  fixtures; the SAT 69-B source is TASK-011.
