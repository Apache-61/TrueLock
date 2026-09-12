# backend/repositories/

**Purpose:** the only place database access happens. Everything else
talks to the database through here.

**What goes here:** query functions returning `domain/entities/` objects,
one repository per aggregate.

**What does not go here:** business logic (→ `backend/services/`), schema
definitions (→ `database/migrations/`, which this module reads against
but does not own).

**Depends on:** `domain/entities/`, and later `database/`.

## Implemented (TASK-001)

- `interfaces.py` — the read surface, as `Protocol`s: `ProviderRepository`,
  `EntityRepository`, `InvoiceRepository`, `PaymentRepository`,
  `TransactionRepository`, `AccountRepository`.
- `memory.py` — in-memory implementations of all six, plus
  `InMemoryRepositories` which holds one of each and loads a mixed stream
  of records by type.

SQL implementations arrive with **TASK-009**, satisfying the same
protocols. Callers do not change.

## Why the interfaces import no driver

`interfaces.py` deliberately imports nothing from `database/` or any
database package, and `tests/unit/test_repositories.py` asserts that by
parsing the file's imports.

That boundary is what lets the agent tools (TASK-005), the detection
pipeline (TASK-019) and the API (TASK-032) be built and tested *before*
the database exists — the same way the frontend shell is built against
its mock. It is also what stops any of them reaching around the
repository into SQL.

So `memory.py` is not a toy. It is the fixture every downstream task
develops against, which is why the query semantics are pinned there once
rather than re-decided per module:

- **Ordering is guaranteed.** Invoices and payments come back by date then
  id; transactions by date then id. The money-flow graph and the trail UI
  both depend on it, and a detector that assumes ordering against a
  repository that does not promise it produces a trail that is wrong
  rather than absent.
- **Periods include both endpoints**, and a reversed period raises rather
  than returning nothing — an empty result would read as "no invoices"
  instead of "bad query".
- **Absence is a normal answer.** An unknown key returns `None` and an
  empty relation returns `[]`; neither raises. An invoice with no payment
  is a *finding*, so it has to be expressible.
- **Negative paging is refused** rather than silently wrapping to the end
  of the list, which is what Python slicing would do.

## Adding a repository method

Add it to the `Protocol` first, then to every implementation. The methods
are the queries the system actually needs, not a generic ORM surface: a
repository that can express any query is one whose cost nobody can reason
about, and these run inside an agent loop that is charged per call.
