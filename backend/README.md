# backend/

**Purpose:** FastAPI service implementing `docs/contracts/api.md` over the
domain/database layer.

**What goes here:** `api/` (route handlers), `services/` (business logic
orchestrating repositories — e.g. assembling a Case view), `repositories/`
(data access over `database/`).

**What does not go here:** detection rules (`detection/`), agent reasoning
(`agent/`), frontend code (`frontend/`). The backend serves data and
triggers investigation runs; it does not itself decide what's suspicious.

**Depends on:** `domain/`, `database/`, `docs/contracts/api.md`.

**Owner:** Agent B (Data/Backend). Empty at bootstrap time — see
`tasks/ready/TASK-001-canonical-ingestion.md` and
`tasks/ready/TASK-002-database-schema.md`.
