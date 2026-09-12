# TASK-051: Hidden fraud scenario: blind end-to-end test

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-049
- **human_authorization:** no

## Objective

Generate a fraud scenario whose answer key no one has seen and run the full pipeline against it blind.

Every other test risks being tuned to its fixture. This is the only one that answers the question the judges will actually ask: does it find fraud it was not built against? Record the honest result whatever it is -- a documented miss is worth more than a tuned pass.

## Allowed paths

```
tests/scenarios/test_blind.py
data/answer_keys/blind/**
```

## Forbidden paths

```
detection/**
backend/**
frontend/**
agent/**
```

## Acceptance criteria

- [ ] The scenario is generated from a seed not used by any other test.
- [ ] The pipeline runs against it with no scenario-specific tuning.
- [ ] The result -- found, partially found, or missed -- is recorded in `history/experiments/` with the numbers.
- [ ] A miss does not fail the build; it is reported. This test measures, it does not gate.

## Tests required

This task is the test. Report the blind result in the PR body.

## Documentation requirements

Record the outcome in `history/experiments/` and summarise it in `docs/testing.md`.
