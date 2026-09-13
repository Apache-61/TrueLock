# Frontend Application (`frontend/`)

**Purpose:** Next.js 14 investigation UI for TrueLock.

## Architecture & Responsibilities

- Renders what the backend API returns via `docs/contracts/api.md`.
- Never owns business logic, fraud scoring, or exposure calculation.
- Typed API client in `frontend/lib/api.ts` maps directly to backend REST endpoints.

## Directory Layout

- `app/` — Next.js App Router entry points (`layout.tsx`, `page.tsx`, `globals.css`).
- `components/` — Modular investigation components:
  - `LeadsDashboard.tsx` — Ranked suspicious leads with risk scoring.
  - `InvestigationTimeline.tsx` — Step-by-step "What the auditor did" trace.
  - `MoneyTrailGraph.tsx` — Visual money trail graph with circular return indicators.
  - `EvidencePanel.tsx` — Collected forensic evidence with provenance hashes.
  - `CaseFileView.tsx` — Case summary, supported/net exposure, citations, and limitations.
  - `JudgeQAPanel.tsx` — Interactive evidence-grounded Q&A panel for judges.
- `lib/` — API client and utility formatters (`api.ts`).
- `types/` — Shared TypeScript interface contracts (`index.ts`).

## Development

```bash
cd frontend
npm install
npm run dev
```
