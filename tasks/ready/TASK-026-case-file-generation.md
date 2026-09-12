# TASK-026: Case file generation

- **type:** feature
- **priority:** P0
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-025
- **human_authorization:** no

## Objective

Generate the `Case` from a completed investigation: the narrative, the findings, the evidence with its provenance, the money trail, and a stated confidence with the reasoning behind it (`docs/contracts/case.md`).

This is the product's actual output -- the artefact a human investigator would act on. Every claim in the narrative must be traceable to evidence; a narrative that reads well but cannot be sourced is the failure mode to design against.

## Allowed paths

```
agent/case/**
agent/prompts/case.md
tests/**
```

## Forbidden paths

```
frontend/**
detection/**
database/**
evidence/**
```

## Acceptance criteria

- [ ] Every claim in the generated narrative cites the evidence supporting it.
- [ ] The case states a confidence and the reasons for it, including what would change the conclusion.
- [ ] A case generated from an investigation that found nothing says so clearly -- it does not manufacture a narrative.
- [ ] The case serializes to the `Case` entity and is persisted.
- [ ] Generation is deterministic given the same investigation state and a fixed model response.

## Tests required

`tests/unit/` with a fixed investigation state; `tests/scenarios/` asserts the case for the demo scenario names the entities in the answer key.

## Documentation requirements

Update `agent/README.md` with the case-generation flow.
