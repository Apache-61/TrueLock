"""`Payment` — settlement of an invoice (`domain/schemas/payment.schema.json`)."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from .base import CanonicalModel


class Payment(CanonicalModel):
    """A payment-complement record settling one invoice.

    Deliberately distinct from `Transaction`: the domain is three layers,
    INVOICE -> PAYMENT -> BANK TRANSACTION, and collapsing them loses the
    exact discrepancies this system exists to find -- an invoice with no
    payment, a payment with no bank movement, a payment whose underlying
    transactions do not sum to it (`docs/contracts/domain.md`, "why three
    layers not one").
    """

    id: str = Field(min_length=1)
    related_invoice_uuid: str = Field(min_length=1)
    payment_date: date
    amount: float
    payment_form: str | None = None
    currency: str = "MXN"
    previous_balance: float | None = None
    remaining_balance: float | None = None
    #: The bank movements that settle this payment. May be empty: a
    #: payment recorded with no traceable transaction is itself a finding.
    transaction_ids: tuple[str, ...] = ()
