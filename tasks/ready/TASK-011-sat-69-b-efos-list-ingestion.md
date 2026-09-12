# TASK-011: SAT 69-B EFOS list ingestion & enrichment

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** data
- **depends_on:** TASK-001
- **human_authorization:** no

## Objective

Ingest the SAT 69-B EFOS list (`docs/regulatory/sat-69b.md`) and expose an enrichment lookup that answers 'is this RFC listed, in what status, as of when'.

The 69-B correlation detector in TASK-004 needs this to be more than a stub. Work from a local fixture copy of the list so the demo never depends on a live SAT endpoint.

## Allowed paths

```
scripts/ingest/efos.py
data/raw/efos/**
tests/**
```

## Forbidden paths

```
domain/schemas/**
detection/**
frontend/**
agent/**
```

## Acceptance criteria

- [ ] An RFC lookup returns the listed status and the date it applied.
- [ ] The status enum matches `domain/enums/efos-status.md` exactly.
- [ ] Lookup is against a local snapshot -- no network call at demo time.
- [ ] An unknown RFC returns 'not listed' rather than raising.

## Tests required

`tests/unit/` for the lookup, including an RFC in each status and an unknown RFC.

## Documentation requirements

Record the snapshot's provenance and date in `data/raw/efos/README.md`.
