"""Bank CSV export -> canonical `Transaction` (and `Account`).

Bank exports are the least standardised source in this system: every
institution names its columns differently. The header map is therefore
explicit and per-source rather than guessed, because guessing which
column holds the amount is exactly the kind of silent error that makes a
money trail wrong rather than absent.

Unmapped columns are ignored, not merged: an export with an extra column
is normal. An export *missing* a required column fails the whole file,
because that is a mapping error, not a data error, and the right response
is to fix the mapping rather than ingest a partial table.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from truelock.domain.models import EntityValidationError, Transaction

from .errors import IngestError, IngestResult, Rejection


@dataclass(frozen=True)
class BankCsvMapping:
    """Which columns of a given bank's export hold the canonical fields."""

    transaction_id: str = "transaction_id"
    from_account: str = "from_account"
    to_account: str = "to_account"
    transaction_date: str = "date"
    amount: str = "amount"
    related_payment_id: str | None = "payment_id"

    def required_columns(self) -> list[str]:
        return [
            self.transaction_id,
            self.from_account,
            self.to_account,
            self.transaction_date,
            self.amount,
        ]


DEFAULT_MAPPING = BankCsvMapping()


def _clean_amount(raw: str) -> str:
    """Strip the presentation a bank added to a number.

    Thousands separators and a currency symbol are formatting, not data,
    so removing them loses nothing. Anything else is left alone and left
    to fail validation -- in particular a parenthesised negative, which
    means different things at different banks and must not be assumed.
    """
    text = (raw or "").strip().replace(",", "").replace("$", "").replace(" ", "")
    return text


def parse_bank_csv(
    path: Path | str, *, mapping: BankCsvMapping = DEFAULT_MAPPING
) -> IngestResult:
    """Normalize a bank CSV export into `Transaction` records."""
    path = Path(path)
    result = IngestResult()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise IngestError(f"cannot read {path}: {error}") from error

    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise IngestError(f"{path} has no header row")

    present = {name.strip() for name in reader.fieldnames}
    missing = [column for column in mapping.required_columns() if column not in present]
    if missing:
        raise IngestError(
            f"{path} is missing required column(s): {', '.join(missing)}. "
            f"Found: {', '.join(sorted(present))}. Fix the BankCsvMapping for this "
            "bank rather than ingesting a partial table."
        )

    for index, row in enumerate(reader, start=2):  # row 1 is the header
        record = {
            "id": (row.get(mapping.transaction_id) or "").strip(),
            "from_account": (row.get(mapping.from_account) or "").strip(),
            "to_account": (row.get(mapping.to_account) or "").strip(),
            "transaction_date": (row.get(mapping.transaction_date) or "").strip(),
            "amount": _clean_amount(row.get(mapping.amount) or ""),
        }
        if mapping.related_payment_id:
            related = (row.get(mapping.related_payment_id) or "").strip()
            if related:
                record["related_payment_id"] = related
        try:
            result.records.append(Transaction.parse(record))
        except EntityValidationError as error:
            result.rejections.append(Rejection(str(path), str(index), str(error)))
    return result
