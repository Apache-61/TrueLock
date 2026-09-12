# CFDI 4.0

Sourcing: `research/sat/README.md`. Implements
`domain/schemas/invoice.schema.json`.

CFDI 4.0 is the current SAT electronic-invoice version; Anexo 20 is the
specification for structure/syntax.

Sources: https://wwwmatnp.sat.gob.mx/consultas/35025/formato-de-factura-electronica-%28anexo-20%29 ·
https://www.sat.gob.mx/minisitio/Factura/emite_materialdeayudaparafactura.htm

## Canonical fields kept machine-readable (not free text)

```
uuid, version, fecha, emisor_rfc, emisor_nombre, receptor_rfc,
receptor_nombre, tipo_comprobante, metodo_pago, forma_pago, moneda,
subtotal, total, impuestos, conceptos[], complementos[]
```

**Open item:** not every field is mandatory in every CFDI context —
validate the mandatory/conditional status against the Anexo 20 XSD before
treating an ingestion failure as a data-quality signal versus a schema
bug. Tracked in `research/sat/README.md` → "Open before freezing."
