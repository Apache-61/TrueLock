# Hosted `.tech` domain — operator runbook

Judges open a URL only. Developers still may use local Compose.

**Production domain:** `truelockfa.tech` / `api.truelockfa.tech`  
(Registrar: Tech Domains — DNS is case-insensitive; use lowercase in URLs.)

## 1. Domain

1. Register or use an existing `*.tech` name at your registrar.
2. Keep DNS management at the registrar (or Cloudflare) ready for Vercel + Render records.

## 2. Backend + Postgres (Render)

Blueprint: [`render.yaml`](../../render.yaml) at repo root.

1. Connect the GitHub repo in Render → apply blueprint.
2. Set secret env on the API service (Dashboard → Environment):
   - `GEMINI_API_KEY` or `GEMINI_KEY_A`…`D`
   - `FRONTEND_ORIGIN=https://truelockfa.tech` (API also allows `https://www.truelockfa.tech`)
   - `HARD_BUDGET_STOP_USD` (optional)
3. Container start runs migrate + seed then uvicorn on `$PORT` (`scripts/render_start.sh`).
4. Note the onrender.com hostname; you will CNAME `api` to it.

## 3. Frontend (Vercel)

1. Import the repo from GitHub.
2. **Root Directory** (Project → Settings → General): set to **`frontend`**.
   Do not leave this as `.` — `next` lives only in `frontend/package.json`.
3. Framework preset: **Next.js** (auto once Root Directory is `frontend`).
4. Environment (Production):
   - `NEXT_PUBLIC_API_URL=https://api.truelockfa.tech`
   - `NEXT_PUBLIC_SITE_URL=https://truelockfa.tech`
5. Build runs `prebuild` → `sync-docs` (reads `../docs` from the full clone).
6. Attach the `.tech` domain in Vercel → Domains (apex + `www`).

Config files: [`frontend/vercel.json`](../../frontend/vercel.json) (used when Root Directory is `frontend`).
The repo-root [`vercel.json`](../../vercel.json) is a fallback only; prefer Root Directory = `frontend`.

## 4. DNS records

| Name | Type | Value |
|------|------|--------|
| `@` | A / ALIAS | Vercel apex target |
| `www` | CNAME | `cname.vercel-dns.com` (or Vercel guidance) |
| `api` | CNAME | `<service>.onrender.com` |

Wait for TLS certificates to become Active.

## 5. Smoke (from a second device)

1. `https://truelockfa.tech/docs` — 5-minute path
2. `https://api.truelockfa.tech/health` and `/ready`
3. Open auditor `/`, start investigation, optional inject-fraud
4. Confirm CORS: browser console has no blocked origin errors

## 6. Docs pack refresh

After the hostname is final:

```bash
cd frontend && npm run sync-docs
# challenge README / INDEX already point at truelockfa.tech
# regenerate dist/docs-pack zip for offline judges
```

Never put Gemini keys or production `DATABASE_URL` in the zip.
