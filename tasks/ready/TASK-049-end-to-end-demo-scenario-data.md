# TASK-049: End-to-end demo scenario: data to case file

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-019, TASK-026, TASK-036
- **human_authorization:** no

## Objective

One scripted run that exercises the whole vertical slice: load a scenario, run detection, take the top lead, investigate it, generate the case, and assert the case names the entities in the answer key.

This is the definition of 'the product works'. It is also the demo rehearsal -- if it passes, the demo path is real; if it is skipped, nobody actually knows.

## Allowed paths

```
tests/e2e/**
scripts/demo/run_demo.py
tests/**
```

## Forbidden paths

```
backend/**
frontend/**
agent/**
detection/**
```

## Acceptance criteria

- [ ] The run goes from empty database to generated case with no manual step.
- [ ] The generated case names the entities the answer key marks as fraudulent.
- [ ] The run reports elapsed time per stage, so the demo's timing is known in advance.
- [ ] It can run against a recorded model response as well as a live one, so it is usable in CI without spending budget.
- [ ] A failure names the stage that failed, not just 'the demo broke'.

## Tests required

This task is the test. Run it against at least two different scenarios.

## Documentation requirements

Update `docs/demo/runbook.md` with the exact commands and expected timings.
