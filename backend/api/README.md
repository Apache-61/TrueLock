# backend/api/

**Purpose:** FastAPI route handlers implementing `docs/contracts/api.md`.

**What goes here:** thin route functions — parse request, call a service
in `backend/services/`, return the response shape from the contract.

**What does not go here:** business logic (→ `backend/services/`), direct
database queries (→ `backend/repositories/`).

**Depends on:** `docs/contracts/api.md`, `backend/services/`.
