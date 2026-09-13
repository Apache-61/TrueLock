# Backend Service (`backend/`)

**Purpose:** FastAPI service and core product logic for TrueLock under `backend/src/truelock/`.

## Package Layout (`backend/src/truelock/`)

- `api/` — FastAPI REST application and routers (`/health`, `/api/leads`, `/api/investigations/start`, `/api/cases/{case_id}/questions`, `/api/scenarios/reset`).
- `agent/` — Google Gemini API integration (`gemini_client.py`), strictly allowlisted read-only tools (`tools.py`), and bounded loop coordinator (`investigator.py`).
- `database/` — Database repositories and session management.
- `detection/` — Deterministic detectors (`DET-ROUND-TRIP-CYCLE`, `DET-RAPID-PASS-THROUGH`, `DET-DUPLICATE-PAYMENT`, `DET-SHARED-ADDRESS-CONTROL`).
- `domain/` — Normalized Pydantic models and JSON schemas (`models/`, `schemas/`).
- `evidence/` — Exposure calculator (root-flow exposure without double-counting edges) and evidence collection with provenance hashes.
- `seeder/` — Deterministic demo scenario generator and data ingestion parsers.
- `services/` — Investigation orchestration and case Q&A services.
- `settings.py` — Typed settings loaded from environment variables (`GEMINI_API_KEY`, `DATABASE_URL`, etc.).

## Running the Backend

```bash
uvicorn truelock.api.app:app --host 0.0.0.0 --port 8000 --reload
```
