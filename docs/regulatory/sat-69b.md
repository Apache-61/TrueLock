# Article 69-B / EFOS

Sourcing: `research/sat/README.md`. This document is the implementation
rule, not the research trail.

## What 69-B covers

A mechanism for cases where a taxpayer issues tax receipts (CFDIs) without
the assets, personnel, infrastructure, or material capacity to actually
perform the operations those receipts describe, or is not located at its
registered address. SAT publishes a list of affected taxpayers and tracks
their procedural state.

Sources: https://www.sat.gob.mx/minisitio/DatosAbiertos/contribuyentes_publicados.html ·
https://wwwmat.sat.gob.mx/consultas/76675/consulta-la-relacion-de-contribuyentes-que-realizan-operaciones-inexistentes

## Implementation rule

Model as `provider.efos_status` (`domain/enums/efos-status.md`):
`PRESUMED | DEFINITIVE | INVALIDATED | FAVORABLE_JUDGMENT | UNKNOWN`.

**Hard rule for every detector, the agent, and the frontend:**
`EFOS_STATUS = DEFINITIVE` is a **signal**, contributing to a
`detector_signal` (`69B_CORRELATION` in `docs/detection/rules.md`), never
a conclusion by itself. The `case.status` field
(`docs/contracts/case.md`) is a separate judgment built from the total
evidence chain.

## Why this is a security/correctness concern, not just a modeling nicety

Mislabeling a real taxpayer's status is a real-world harm. See
`SECURITY.md` → "Regulatory data handling."
