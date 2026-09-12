# TASK-019: Detection pipeline runner: records to scored leads

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-004, TASK-009, TASK-010
- **human_authorization:** no

## Objective

One entry point that runs every registered detector over a loaded scenario, scores the signals into `Lead`s, and persists them via the TASK-009 repositories.

This is the step that turns detection from a library into a product stage: after it runs, the database holds leads the API can serve and the agent can investigate. It is on the critical path to the vertical slice.

## Allowed paths

```
detection/pipeline.py
scripts/demo/run_detection.py
tests/**
```

## Forbidden paths

```
detection/rules/**
detection/graph/**
frontend/**
agent/**
data/answer_keys/**
```

## Acceptance criteria

- [ ] Running the pipeline on the demo scenario produces persisted, scored leads.
- [ ] A detector that raises is isolated: the pipeline records the failure and continues with the others, rather than losing the whole run.
- [ ] The run reports per-detector counts and elapsed time.
- [ ] Re-running is idempotent -- it does not duplicate leads for signals already recorded.
- [ ] Leads are ordered by score, so the top lead is the one the demo opens with.

## Tests required

`tests/integration/` runs the pipeline over a loaded scenario and asserts leads land in the database; `tests/scenarios/` asserts the top leads match the answer key.

## Documentation requirements

Update `detection/README.md` with how to run the pipeline.
