End-to-end tests (Fase 6): `dataset → detector → lead → agent → case → API`.

| File | Coverage |
|---|---|
| `test_canonical_flow.py` | Canonical cycle + control via service + HTTP |
| `test_inject_offline_and_eval.py` | Inject-fraud, offline fallback, promotion gate |
| `test_postgres_flow.py` | Optional Postgres seed → investigate → API |

Frontend component logic is covered under `frontend` unit tests for Q&A UI
helpers (evidence refs / empty state). Full browser E2E can be added later
with Playwright; the API contract the UI consumes is gated here.

```bash
PYTHONPATH=backend/src pytest -q tests/e2e/
PYTHONPATH=backend/src python scripts/eval_agent.py
```
