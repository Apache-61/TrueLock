# TASK-052: Deployment: one-command local stack

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** infra
- **depends_on:** none
- **human_authorization:** no

## Objective

A single command that brings up database, backend and frontend together from a clean checkout, so any of the four machines -- and the demo machine -- runs an identical stack.

Has no code dependencies: it can be built now, in parallel with everything else.

## Allowed paths

```
deployment/**
docker-compose.yml
Makefile
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

- [ ] One command brings the stack up from a clean checkout.
- [ ] Services wait for their dependencies rather than racing and crashing on first start.
- [ ] Ports and env vars are documented in one place.
- [ ] Bringing the stack down and up again preserves the loaded demo data, or documents clearly that it does not.

## Tests required

A smoke script that brings the stack up, hits health, and tears it down.

## Documentation requirements

Document the commands in `docs/deployment.md`.
