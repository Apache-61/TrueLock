"""`Transaction` — a bank movement (`domain/schemas/transaction.schema.json`)."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from .base import CanonicalModel


class Transaction(CanonicalModel):
    """Account-to-account movement of money: the money-flow graph's edge.

    `related_payment_id` is nullable on purpose. A hop between shell
    accounts has no invoice behind it, and those unexplained hops are
    exactly what the fan-in/fan-out, cycle and pass-through detectors
    look for (`research/graph/README.md`).
    """

    id: str = Field(min_length=1)
    from_account: str = Field(min_length=1)
    to_account: str = Field(min_length=1)
    transaction_date: date
    amount: float
    related_payment_id: str | None = None
