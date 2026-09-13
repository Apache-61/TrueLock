Scenario regression fixtures for each fraud pattern in `docs/detection/rules.md`.

Synthetic builders live in `truelock.seeder.detector_scenarios`.
Answer keys live in `data/answer_keys/*_answer_key.json`.
Agent evaluation packs live in `data/eval_corpus/` (never imported by runtime).

Run:

```bash
PYTHONPATH=backend/src pytest -q tests/scenarios tests/unit/test_detection.py
```
