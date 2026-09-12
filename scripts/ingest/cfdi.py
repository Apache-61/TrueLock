"""CFDI 4.0 XML -> canonical `Invoice`.

Reads only the fields `domain/schemas/invoice.schema.json` declares. A
CFDI carries far more than this; the rest is deliberately not invented
into the canonical record, because a field nobody validated is a field
nobody should reason about.

Namespace handling is lenient (the `cfdi:` prefix is conventional, not
guaranteed) but *field* handling is strict: a missing required attribute
or an unparseable value rejects the record rather than defaulting it.

This is a reader for the canonical subset, not a CFDI validator. Anexo 20
XSD validation is a separate concern and is noted in
`docs/regulatory/cfdi-40.md`.
"""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from domain.entities import EntityValidationError, Invoice

from .errors import IngestError, IngestResult, Rejection

#: CFDI attribute -> canonical field. The Spanish names are the wire
#: format; the canonical names are what the rest of the system uses.
COMPROBANTE_FIELDS = {
    "Version": "version",
    "Fecha": "issue_date",
    "Total": "amount",
    "SubTotal": "subtotal",
    "Moneda": "currency",
    "MetodoPago": "payment_method",
    "FormaPago": "payment_form",
    "TipoDeComprobante": "cfdi_type",
}


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_child(element, name: str):
    for child in element.iter():
        if _localname(child.tag) == name:
            return child
    return None


def invoice_from_element(element) -> Invoice:
    """Build one `Invoice` from a `<Comprobante>` element.

    Raises `EntityValidationError` if the result is not a valid invoice —
    the caller decides whether that rejects one record or the whole file.
    """
    record: dict = {}
    for attribute, canonical in COMPROBANTE_FIELDS.items():
        value = element.get(attribute)
        if value is not None and value != "":
            record[canonical] = value

    # Fecha is a datetime in CFDI ("2026-01-15T10:30:00"); the canonical
    # contract is a date. Truncating is safe and documented; parsing the
    # whole thing as a date is not.
    if isinstance(record.get("issue_date"), str) and "T" in record["issue_date"]:
        record["issue_date"] = record["issue_date"].split("T", 1)[0]

    emisor = _find_child(element, "Emisor")
    receptor = _find_child(element, "Receptor")
    if emisor is not None and emisor.get("Rfc"):
        record["provider_rfc"] = emisor.get("Rfc")
    if receptor is not None and receptor.get("Rfc"):
        record["receiver_rfc"] = receptor.get("Rfc")

    timbre = _find_child(element, "TimbreFiscalDigital")
    if timbre is not None and timbre.get("UUID"):
        record["uuid"] = timbre.get("UUID")

    impuestos = _find_child(element, "Impuestos")
    if impuestos is not None and impuestos.get("TotalImpuestosTrasladados"):
        record["taxes"] = impuestos.get("TotalImpuestosTrasladados")

    concepts = [
        child.get("Descripcion")
        for child in element.iter()
        if _localname(child.tag) == "Concepto" and child.get("Descripcion")
    ]
    if concepts:
        record["concept"] = "; ".join(concepts)

    return Invoice.parse(record)


def parse_cfdi_file(path: Path | str) -> IngestResult:
    """Normalize one CFDI XML file into at most one `Invoice`."""
    path = Path(path)
    result = IngestResult()
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError as error:
        # Unreadable XML is one bad record, not an unusable source: a
        # directory of thousands should not fail because one is corrupt.
        result.rejections.append(Rejection(str(path), "1", f"not well-formed XML: {error}"))
        return result
    except OSError as error:
        raise IngestError(f"cannot read {path}: {error}") from error

    try:
        result.records.append(invoice_from_element(tree.getroot()))
    except EntityValidationError as error:
        result.rejections.append(Rejection(str(path), "1", str(error)))
    return result


def parse_cfdi_directory(directory: Path | str, *, pattern: str = "*.xml") -> IngestResult:
    """Normalize every CFDI in a directory, keeping going past bad ones."""
    directory = Path(directory)
    if not directory.is_dir():
        raise IngestError(f"not a directory: {directory}")
    combined = IngestResult()
    for path in sorted(directory.glob(pattern)):
        one = parse_cfdi_file(path)
        combined.records.extend(one.records)
        combined.rejections.extend(one.rejections)
    return combined
