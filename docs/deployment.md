# Deployment

**Status:** not yet implemented — this documents intent, to be filled in
as `backend/` and `frontend/` exist.

## Target for the demo

- Frontend: static/SSR Next.js build, hosted on the Best .Tech sponsor
  domain (`research/infrastructure/README.md` → sponsor integration
  order).
- Backend: FastAPI, containerized, pointed at PostgreSQL.
- Fallback: if the sponsor domain/hosting is unavailable at demo time,
  run everything locally on the demo laptop — see
  `research/infrastructure/README.md` → "Fallback matrix" (Cloud host →
  local/server fallback).

## What must never happen automatically

Per `CONTRIBUTING.md` §5, deploying to the demo environment requires
human authorization — no CI job auto-deploys on merge to `main` for this
build. `main` being green and mergeable is necessary but not sufficient
for a deploy.

## Environment variables

See `.env.example` for the full list and `SECURITY.md` for secret
handling.
