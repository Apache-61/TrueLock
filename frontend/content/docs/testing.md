# Testing strategy

## Levels

- **Unit** (`tests/unit/`) — detectors, agent policy helpers, import parsers, API wiring without Postgres.
- **Contract** (`tests/contract/`) — schemas, agent tool envelopes, demo/API response shapes in `docs/contracts/`.
- **Integration** (`tests/integration/`) — PostgreSQL repositories, import persistence, health/ready with `DATABASE_URL`.
- **End-to-end** (`tests/e2e/`) — investigation start → evidence → Q&A; Postgres-backed flow when a DB is available.
- **Scenario / eval** (`data/eval_corpus/`, `scripts/eval_agent.py`) — blocked promotion packs against policy expectations.
- **Frontend helpers** (`frontend/__tests__/`) — grounded Q&A UI guards. Opt-in Playwright smoke: `frontend/e2e`.

## Baseline (current product)

Passing locally means at least:

```bash
bash scripts/check_requirements.sh
pytest -q
python scripts/verify_demo.py
python scripts/verify_recovery.py
python scripts/eval_agent.py
cd frontend && npm test && npm run build
```

With Docker Postgres (host port **5433** to avoid a local Windows PostgreSQL on 5432):

```bash
docker compose up -d postgres
docker compose --profile app run --rm migrate
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
export TRUELOCK_TEST_DATABASE_URL="$DATABASE_URL"
pytest -q
bash scripts/test_database.sh
```

On Windows, prefer the Compose `migrate` service: native `psql.exe` often mishandles URI connection strings. `psql` on `PATH` is still useful for ad-hoc queries once `DATABASE_URL` uses host `localhost` and port `5433`.

CI installs `postgresql-client`, starts Postgres on **5432** inside the runner network, migrates/seeds, and runs the full pytest suite — see `.github/workflows/ci.yml`.

## Opt-in live provider tests

Live Gemini / Claude worker tests stay skipped unless their env flags are set; they call paid APIs.
