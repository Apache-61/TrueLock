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
pip install -r requirements-dev.txt   # once it exists (TASK-00x)
pytest
```

CI runs the same command on every PR — see `.github/workflows/ci.yml`.
