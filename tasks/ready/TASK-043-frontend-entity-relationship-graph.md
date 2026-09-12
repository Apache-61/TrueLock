# TASK-043: Frontend: entity relationship graph

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** frontend
- **depends_on:** TASK-006, TASK-034
- **human_authorization:** no

## Objective

Render the entity/account graph around an investigation with Cytoscape.js (the default in `ARCHITECTURE.md`): nodes for entities, edges for flows, with the suspicious subgraph highlighted and every node clickable through to its profile.

## Allowed paths

```
frontend/app/graph/**
frontend/components/graph/**
tests/**
```

## Forbidden paths

```
frontend/app/layout.tsx
backend/**
detection/**
agent/**
```

## Acceptance criteria

- [ ] The demo-scale graph renders and stays interactive (document the node count it was tested at).
- [ ] The subgraph the investigation implicates is visually distinct from background entities.
- [ ] Clicking a node opens that entity's profile.
- [ ] A graph too large to render usefully is summarised or filtered rather than drawn as a hairball.

## Tests required

Component tests for rendering a fixture graph, the highlight, and the oversized-graph path.

## Documentation requirements

Update `frontend/README.md` with the library choice and why.
