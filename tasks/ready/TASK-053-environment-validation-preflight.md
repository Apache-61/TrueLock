# TASK-053: Environment validation preflight

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** infra
- **depends_on:** none
- **human_authorization:** no

## Objective

One command that checks a machine is actually ready: required env vars present and non-empty, database reachable, model key valid, Python and Node versions supported.

Run before the demo. Discovering a missing key in front of judges is a preventable failure.

## Allowed paths

```
scripts/validate/**
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

- [ ] Every check reports pass or fail with the exact remedy for a failure.
- [ ] A missing model key is reported without printing the value of any secret.
- [ ] The command exits non-zero when any required check fails.
- [ ] It runs in seconds and needs no arguments.

## Tests required

`tests/unit/` for each check against a simulated broken environment.

## Documentation requirements

Document the preflight in `docs/deployment.md` and `docs/demo/runbook.md`.
