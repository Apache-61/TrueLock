# SAT / regulatory research

Source status tags per `research/README.md`. This informs the modeling
rules enforced in `docs/regulatory/` and `domain/enums/efos-status.md` —
read those for the actual data-model consequence; this file is the
supporting research.

## Article 69-B (FACT / OFFICIAL)

The SAT explains Article 69-B as covering cases where a taxpayer issues tax
receipts without the assets, personnel, infrastructure, or material
capacity to perform the operations those receipts describe, or is not
located. SAT publishes the related taxpayer list and distinguishes
procedural states.

Sources:
- https://www.sat.gob.mx/minisitio/DatosAbiertos/contribuyentes_publicados.html
- https://wwwmat.sat.gob.mx/consultas/76675/consulta-la-relacion-de-contribuyentes-que-realizan-operaciones-inexistentes
- Código Fiscal de la Federación (CFF): https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf

## INFERENCE — required internal representation

A 69-B listing is **fiscal status/evidence**, not an automatic fraud label.
Required states:

```
EFOS_STATUS
    PRESUMED
    DEFINITIVE
    INVALIDATED / DESVIRTUED
    FAVORABLE_JUDGMENT
    UNKNOWN
```

**Do not** model `EFOS = FRAUD`. **Do** model
`EFOS_STATUS = DEFINITIVE + RELATION_TO_ENTITY = observed`, and keep the
final forensic judgment as a separate conclusion built from total evidence
(`docs/contracts/case.md`).

## CFDI 4.0 (FACT / OFFICIAL, with INFERENCE on field mandatoriness)

SAT identifies CFDI 4.0 as the current invoice version; Anexo 20 is the
specification for structure/syntax.

Sources:
- https://wwwmatnp.sat.gob.mx/consultas/35025/formato-de-factura-electronica-%28anexo-20%29
- https://www.sat.gob.mx/minisitio/Factura/emite_materialdeayudaparafactura.htm

Candidate canonical fields (machine-readable, not free text):

```
uuid, version, fecha, emisor_rfc, emisor_nombre, receptor_rfc,
receptor_nombre, tipo_comprobante, metodo_pago, forma_pago, moneda,
subtotal, total, impuestos, conceptos[], complementos[]
```

**INFERENCE / open item:** not every field is mandatory in every CFDI
context — mandatory/conditional status must be validated against the XSD
and SAT documentation before the schema in `domain/schemas/invoice.schema.json`
is treated as final.

## Payment complement (FACT / OFFICIAL)

SAT's payment-complement materials expose payment date, form, currency,
amount, related invoice UUID, payment method, installment info, previous
balance, amount paid, and remaining balance — meaning the model must keep
`INVOICE → PAYMENT → BANK TRANSACTION` as three distinct entities, never
collapsed into one "financial transaction" (see
`docs/contracts/domain.md`).

## Open before freezing

- [ ] Official challenge PDF not yet available to this session — see
      `docs/challenge/README.md`. Reconcile any scoring-specific
      requirement against it before treating anything here as final.
- [ ] CFDI field mandatoriness needs XSD validation.
- [ ] A cached local snapshot of the 69-B list and CFDI docs should be
      pulled before the main build starts (offline resilience — see
      `research/datasets/README.md` §Offline caching checklist).
