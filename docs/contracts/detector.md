# Contract: Detector

A detector is a deterministic function: canonical data in, zero or more
`domain/schemas/detector_signal.schema.json` records out. See
`docs/detection/rules.md` for the actual pattern library; this file is the
interface every detector must implement.

## Interface

```python
def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Pure function. Same input -> same output, always.
    Must not call any LLM, network service, or the agent.
    Must attach source_ids for every signal it emits.
    """
```

- **Pure and deterministic.** No randomness, no network calls, no model
  calls. A detector's output must be reproducible for tests and for a
  judge's "run it again" moment.
- **Cites its sources.** Every `DetectorSignal.source_ids` must point to
  real record IDs (invoice UUIDs, transaction IDs) in the dataset.
- **One responsibility.** A detector implements exactly one pattern from
  `docs/detection/rules.md`'s table (e.g. `DUPLICATE_INVOICE`, not
  "general weirdness").
- **No pursue/discard decision.** That's the Lead-aggregation step's job
  (`docs/contracts/leads.md`), not the detector's.

## Registration

Detectors register themselves in `detection/rules/__init__.py`'s registry
(implemented as part of `TASK-004`) so the scoring step
(`detection/scoring/`) can run all of them uniformly and so new detectors
don't require touching orchestration code.

## Testing

Every detector needs: a unit test with a synthetic positive case, a
synthetic negative case (data that looks similar but should NOT fire), and
a scenario fixture under `tests/scenarios/` with an answer key
(`data/answer_keys/`). See `docs/testing.md`.

## Ownership

Detection Pipeline Layer (`backend/src/truelock/detection/detectors.py`).
