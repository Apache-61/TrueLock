# Hosted `.tech` domain — operator runbook

Judges open a URL only. Developers still may use local Compose.

**Placeholder domain:** `truelock.tech` / `api.truelock.tech`  
Change these strings if your purchased hostname differs.

## 1. Domain

1. Register or use an existing `*.tech` name at your registrar.
2. Keep DNS management at the registrar (or Cloudflare) ready for Vercel + Render records.

## 2. Backend + Postgres (Render)

Blueprint: [`render.yaml`](../../render.yaml) at repo root.

1. Connect the GitHub repo in Render → apply blueprint.
2. Set secret env on the API service (Dashboard → Environment):
   - `GEMINI_API_KEY` or `GEMINI_KEY_A`…`D`
   - `FRONTEND_ORIGIN=https://truelock.tech`
   - `HARD_BUDGET_STOP_USD` (optional)
3. Release command runs migrations + seed (see `render.yaml`).
4. Note the onrender.com hostname; you will CNAME `api` to it.

## 3. Frontend (Vercel)

Config: [`vercel.json`](../../vercel.json).

1. Import the repo; set **Root Directory** to `frontend` *or* use the
   install/build commands in `vercel.json` from the monorepo root.
2. Environment:
   - `NEXT_PUBLIC_API_URL=https://api.truelock.tech`
   - `NEXT_PUBLIC_SITE_URL=https://truelock.tech`
3. Build runs `npm run sync-docs` via `prebuild` so markdown is embedded.
4. Attach the `.tech` domain in Vercel → Domains (apex + `www`).

## 4. DNS records

| Name | Type | Value |
|------|------|--------|
| `@` | A / ALIAS | Vercel apex target |
| `www` | CNAME | `cname.vercel-dns.com` (or Vercel guidance) |
| `api` | CNAME | `<service>.onrender.com` |

Wait for TLS certificates to become Active.

## 5. Smoke (from a second device)

1. `https://truelock.tech/docs` — 5-minute path
2. `https://api.truelock.tech/health` and `/ready`
3. Open auditor `/`, start investigation, optional inject-fraud
4. Confirm CORS: browser console has no blocked origin errors

## 6. Docs pack refresh

After the hostname is final:

```bash
cd frontend && npm run sync-docs
# update challenge README / INDEX if the domain changed from truelock.tech
# regenerate dist/docs-pack zip for offline judges
```

Never put Gemini keys or production `DATABASE_URL` in the zip.
