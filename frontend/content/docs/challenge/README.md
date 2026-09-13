# Challenge — Judge / reviewer index

**Preferred surface (hosted):** [https://truelockfa.tech/docs](https://truelockfa.tech/docs)
(replace with your live `.tech` hostname once DNS is pointed). Judges need only a browser.

**Start here** if you are reviewing or judging TrueLock. This page is the
entry point; follow the links in order for a ~5-minute path.

## 5-minute path

| Step | Where (webpage) | Markdown (offline pack) | What you get |
|------|-----------------|-------------------------|--------------|
| 1. Start | [/docs](/docs) | This page | Scope, ports, and links |
| 2. Run | [/docs/runbook](/docs/runbook) | [`docs/demo/runbook.md`](../demo/runbook.md) | Live demo flow + inject-fraud |
| 3. Script | [/docs/demo-script](/docs/demo-script) | [`docs/demo-script.md`](../demo-script.md) | Spoken walkthrough (~3–5 min) |
| 4. Contracts | [/docs/api](/docs/api) | [`docs/contracts/api.md`](../contracts/api.md) | REST surface (`/api/imports/*`, `/demo/inject-fraud`) |
| 5. Training overview | [/docs/training](/docs/training) | [`docs/agent/training.md`](../agent/training.md) | Policy / eval promotion (read-only overview) |

Supporting maps:

- [`traceability-matrix.md`](traceability-matrix.md) — [/docs/traceability](/docs/traceability)
- [`docs/deployment.md`](../deployment.md) — [/docs/deployment](/docs/deployment) (Compose + cloud `.tech`)
- [`docs/testing.md`](../testing.md) — [/docs/testing](/docs/testing)

Upload pack (copies + zip): `dist/docs-pack/` — see `dist/docs-pack/INDEX.md`.

## Ports

### Hosted (judges — nothing to install)

| Service | URL |
|---------|-----|
| App + docs | `https://truelockfa.tech` (and `/docs`) |
| API | `https://api.truelockfa.tech` |

### Local developer only

| Service | Host |
|---------|------|
| Frontend | `http://localhost:3000` (docs at `/docs`) |
| API | `http://localhost:8000` (OpenAPI: `/docs` on the API process) |
| Postgres | **`localhost:5433`** → container `5432` (`docker-compose.yml`) |

```bash
docker compose up -d postgres
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
```

## API highlights judges care about

From [`docs/contracts/api.md`](../contracts/api.md):

- `POST /api/imports/cfdi` · `POST /api/imports/bank` · `POST /api/imports/efos`
- `POST /demo/inject-fraud` — inject a hidden scenario; watch detectors / investigation
- `POST /api/investigations/start` · `POST /api/cases/{case_id}/questions`

## Working requirement summary

The system must find fraud signals, investigate them, follow money and
relationships, build an evidence chain, justify leads, sustain or reject
accusations, produce a human-readable case file, and answer grounded Q&A.
The demo must let judges introduce or hide a fraud pattern
(`POST /demo/inject-fraud`) and watch the agent respond.

## Publish / share (no secrets)

Remote: `https://github.com/Apache-61/TrueLock.git`

```bash
# Prefer a clean branch push of docs-only commits when ready (do not commit .env)
git push -u origin HEAD

# Or hand judges the zip without git:
# dist/truelock-docs-pack.zip
```

Never commit `.env`, API keys, or real credentials. Use `.env.example` only.
