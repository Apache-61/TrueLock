# TASK-041: Frontend: investigation timeline

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-037
- **human_authorization:** no

## Objective

Render an investigation as an ordered timeline: each step, the tool called, what it returned, and the evidence it produced -- the view that shows the investigation was reasoned, not guessed.

## Allowed paths

```
frontend/app/investigation/**
frontend/components/timeline/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] Steps render in order with their tool, arguments and result summary.
- [ ] A running investigation renders its partial timeline and indicates it is still going.
- [ ] Each step links to the evidence and source records behind it.
- [ ] A long investigation stays readable -- the timeline does not require horizontal scrolling.

## Tests required

Component tests for running, complete and empty investigations.

## Documentation requirements

Update `frontend/README.md`.
