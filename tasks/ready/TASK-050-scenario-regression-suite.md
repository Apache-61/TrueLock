# TASK-050: Scenario regression suite

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** detection
- **depends_on:** TASK-019
- **human_authorization:** no

## Objective

Lock in detector quality: for every scenario, assert precision and recall against the answer key and fail the build when either regresses beyond a documented tolerance.

Detectors get tuned under time pressure. This is what stops a tweak that fixes one scenario from quietly breaking two others.

## Allowed paths

```
tests/scenarios/test_regression.py
```

## Forbidden paths

```
detection/**
backend/**
frontend/**
agent/**
```

## Acceptance criteria

- [ ] Per-scenario, per-detector precision and recall are asserted against documented baselines.
- [ ] A regression names the detector and the scenario that regressed.
- [ ] Baselines live in one place and changing one is a visible diff.
- [ ] The suite runs without a model key.

## Tests required

This task is the tests. Demonstrate a deliberate regression failing the suite.

## Documentation requirements

Update `docs/testing.md` with the baselines and how to change one.
