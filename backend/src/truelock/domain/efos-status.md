# EFOS status enum

Backing research: `research/sat/README.md`. This enum is used by
`domain/schemas/provider.schema.json`.

```
EFOS_STATUS
    PRESUMED            -- SAT has published a presumptive listing
    DEFINITIVE          -- SAT has confirmed the listing (CFF Art. 69-B)
    INVALIDATED         -- the taxpayer successfully "desvirtuó" the presumption
    FAVORABLE_JUDGMENT   -- a court ruled in the taxpayer's favor
    UNKNOWN             -- no 69-B record found / not checked
```

## The one rule that matters

```
EFOS_STATUS = DEFINITIVE  ≠  FRAUD
```

A `DEFINITIVE` EFOS status is one signal among several
(`docs/contracts/leads.md`), never a standalone conclusion. It becomes
relevant to a case only combined with an observed relationship to the
entity under investigation:

```
EFOS_STATUS = DEFINITIVE + RELATION_TO_ENTITY = observed
→ a detector_signal, feeding a lead, feeding (maybe) evidence
```

The final `case.schema.json` conclusion (`SUBSTANTIATED` /
`UNSUBSTANTIATED` / `INSUFFICIENT_EVIDENCE`) is a separate forensic
judgment built from the total accumulated evidence, never auto-derived
from EFOS status alone.
