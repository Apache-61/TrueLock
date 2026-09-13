"""EFOS / SAT 69-B snapshot CSV -> contextual regulatory records.

Importing this list must never flip a case outcome by itself. The rows are
provenance for circumstantial context only.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .errors import IngestError, IngestResult, Rejection

_STATUS_MAP = {
    "PRESUNTO": "PRESUNTO",
    "PRESUMED": "PRESUNTO",
    "DEFINITIVO": "DEFINITIVO",
    "DEFINITIVE": "DEFINITIVO",
    "DESVIRTUADO": "DESVIRTUADO",
    "INVALIDATED": "DESVIRTUADO",
    "SENTENCIA_FAVORABLE": "SENTENCIA_FAVORABLE",
    "FAVORABLE_JUDGMENT": "SENTENCIA_FAVORABLE",
    "NOT_FOUND": "NOT_FOUND",
}


@dataclass(frozen=True)
class EfosRecord:
    """One normalized SAT 69-B row with provenance metadata."""

    rfc: str
    legal_name: str | None
    status: str
    snapshot_date: date
    source_locator: str
    publication_reference: str | None = None
    raw_status_text: str | None = None


def _parse_date(value: str) -> date:
    text = (value or "").strip()
    if not text:
        raise ValueError("snapshot_date is required")
    if "T" in text:
        text = text.split("T", 1)[0]
    return date.fromisoformat(text)


def parse_efos_69b_csv(path: Path | str, *, snapshot_date: date | None = None) -> IngestResult:
    """Normalize a SAT 69-B CSV export. Does not mutate case fraud state."""
    path = Path(path)
    result = IngestResult()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise IngestError(f"cannot read {path}: {error}") from error

    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise IngestError(f"{path} has no header row")

    present = {name.strip().lower(): name.strip() for name in reader.fieldnames}
    required = ["rfc", "status"]
    missing = [column for column in required if column not in present]
    if missing:
        raise IngestError(
            f"{path} is missing required column(s): {', '.join(missing)}. "
            f"Found: {', '.join(sorted(present))}."
        )

    for index, row in enumerate(reader, start=2):
        locator = str(index)
        try:
            rfc = (row.get(present["rfc"]) or "").strip().upper()
            if not rfc:
                raise ValueError("rfc is required")
            raw_status = (row.get(present["status"]) or "").strip()
            status = _STATUS_MAP.get(raw_status.upper())
            if not status:
                raise ValueError(f"unknown EFOS status {raw_status!r}")
            name_key = present.get("legal_name") or present.get("nombre")
            legal_name = (row.get(name_key) or "").strip() if name_key else None
            date_key = present.get("snapshot_date") or present.get("fecha")
            row_date = snapshot_date
            if date_key and (row.get(date_key) or "").strip():
                row_date = _parse_date(row.get(date_key) or "")
            if row_date is None:
                row_date = date.today()
            pub_key = present.get("publication_reference")
            publication = (row.get(pub_key) or "").strip() if pub_key else None
            result.records.append(
                EfosRecord(
                    rfc=rfc,
                    legal_name=legal_name or None,
                    status=status,
                    snapshot_date=row_date,
                    source_locator=locator,
                    publication_reference=publication or None,
                    raw_status_text=raw_status,
                )
            )
        except (ValueError, TypeError) as error:
            result.rejections.append(Rejection(str(path), locator, str(error)))
    return result
