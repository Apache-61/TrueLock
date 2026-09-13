# Testing strategy

## Levels

- **Unit** (`tests/unit/`) — every detector, in isolation, against
  synthetic positive and negative cases.
- **Contract** (`tests/contract/`) — every interface in
  `docs/contracts/`: JSON Schema validity, API response shape, tool
  response shape (`result`/`provenance`/`source_ids`/`execution_time`/
  `errors`).
- **Integration** (`tests/integration/`) — `detector → lead → tool →
  evidence`, i.e. does a signal actually turn into a followable lead that
  produces real evidence.
- **End-to-end** (`tests/e2e/`) — `dataset → detector → agent → case →
  frontend`, the full loop.
- **Scenario regression** (`tests/scenarios/`) — one fixture per fraud
  pattern in `docs/detection/rules.md`, each with:

  ```
  scenario, expected_leads, expected_path, expected_evidence,
  expected_amount, expected_conclusion, expected_discarded_leads
  ```

  The hidden judge scenario gets an answer key in `data/answer_keys/`
  that the agent never sees (see `docs/demo/runbook.md` → "hidden-fraud
  moment").

## Baseline

At bootstrap time, "passing" means: every JSON Schema file in
`domain/schemas/` is valid, and the task-queue/fixture files that exist
are well-formed. See `tests/contract/test_schemas.py`. This is intentionally
minimal — there is no product code yet to test beyond its contracts.

## Running

```bash
pip install -e ".[dev]"
bash scripts/check_requirements.sh
pytest
```

### PostgreSQL integration tests

Database integration tests require **`psql`** and a reachable PostgreSQL instance:

```bash
docker compose up -d postgres
export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5432/truelock'
export TRUELOCK_TEST_DATABASE_URL="$DATABASE_URL"
bash scripts/migrate.sh
pytest -v tests/integration/test_database.py
```

CI installs `postgresql-client`, starts a Postgres service container, runs the migration/seed/invariant scripts, and executes the full pytest suite on every PR — see `.github/workflows/ci.yml`.

### Opt-in tests that cost money

`tests/integration/test_worker_live_claude.py` drives the AI development
worker against the **real** Claude Code CLI. It is skipped unless you ask
for it, because it calls a paid API and takes a minute or two:

```bash
WORKER_LIVE_AI_TEST=1 pytest -q tests/integration/test_worker_live_claude.py
```

It builds a throwaway git repository, gives the AI a small real task, and
checks what came back — including running the AI's own code rather than
trusting the status it reported. The GitHub side stays in-memory, so it
never touches the real repository.

Everything else about the worker is covered offline in `tests/unit/`. Run
the live test after changing the adapter, and when the Claude Code CLI
has been upgraded: what only it can prove is that the CLI is still
invoked correctly and that its JSON envelope still parses.
