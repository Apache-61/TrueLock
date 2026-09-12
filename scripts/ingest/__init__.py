"""Ingestion: raw source formats -> canonical records.

One parser per source format, all following the same rule from
`SECURITY.md`: **reject a malformed record, never best-effort-guess it.**
Each returns an `IngestResult` carrying both what was accepted and every
rejection with its reason and location, because the records a source
could not produce are themselves a finding.
"""
from __future__ import annotations

from .bank_csv import DEFAULT_MAPPING, BankCsvMapping, parse_bank_csv
from .cfdi import invoice_from_element, parse_cfdi_directory, parse_cfdi_file
from .errors import IngestError, IngestResult, Rejection

__all__ = [
    "BankCsvMapping",
    "DEFAULT_MAPPING",
    "IngestError",
    "IngestResult",
    "Rejection",
    "invoice_from_element",
    "parse_bank_csv",
    "parse_cfdi_directory",
    "parse_cfdi_file",
]
