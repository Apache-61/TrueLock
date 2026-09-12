# TASK-048: Frontend/backend contract tests

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** backend
- **depends_on:** TASK-033, TASK-037
- **human_authorization:** no

## Objective

Pin the API contract from both sides: assert the served OpenAPI matches `docs/contracts/api.md`, and that the frontend's mock fixtures match the same shapes.

Without this, the mock and the real API drift and the integration fails at the worst possible moment -- during the demo.

## Allowed paths

```
tests/contract/test_api_contract.py
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

- [ ] A breaking change to any documented endpoint shape fails this suite.
- [ ] The frontend mock fixtures are validated against the same schemas as the real responses.
- [ ] The suite runs without a database or a model key.

## Tests required

This task is the tests. It must fail when a contract is broken -- demonstrate that in the PR.

## Documentation requirements

Update `docs/testing.md` with the contract level.
