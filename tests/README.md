# tests/

See `docs/testing.md` for the full strategy. Layout:

- `unit/` — one detector/function in isolation.
- `contract/` — every interface in `docs/contracts/` (schema validity, API
  shape, tool response shape). `test_schemas.py` here is the bootstrap
  baseline (see `PROJECT_STATE.md`).
- `integration/` — `detector → lead → tool → evidence`.
- `e2e/` — `dataset → detector → agent → case → frontend`.
- `scenarios/` — one fixture per fraud pattern, with an answer key in
  `data/answer_keys/`.

Run with `pytest` from the repo root. CI runs the same
(`.github/workflows/ci.yml`).
