# backend/repositories/

**Purpose:** the only place SQL/database access happens. Everything else
talks to the database through here.

**What goes here:** query functions returning `domain/entities/` objects,
one repository per aggregate (providers, invoices, payments, transactions,
cases).

**What does not go here:** business logic (→ `backend/services/`), schema
definitions (→ `database/migrations/`, which this module reads against
but does not own).

**Depends on:** `database/`, `domain/entities/`.
