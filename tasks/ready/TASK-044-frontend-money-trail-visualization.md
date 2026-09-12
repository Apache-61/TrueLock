# TASK-044: Frontend: money trail visualization

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-037
- **human_authorization:** no

## Objective

Render the traced money path from the TASK-028 tool results: each hop with amount, date and counterparty, showing where the money went and how much was retained at each step.

## Allowed paths

```
frontend/app/money-trail/**
frontend/components/money-trail/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Each hop shows amount, date, counterparty and a link to the source record.
- [ ] Amounts are formatted as currency with the correct locale.
- [ ] A trail that hits its depth bound says so, rather than implying the trail ended.
- [ ] An empty trail renders an explicit empty state.

## Tests required

Component tests for a multi-hop trail, a depth-bounded trail, and an empty one.

## Documentation requirements

Update `frontend/README.md`.
