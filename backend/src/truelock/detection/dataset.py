"""Canonical dataset view used by pure detector functions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone

from truelock.database.repositories.interfaces import (
    AccountRepository,
    EntityRepository,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)
from truelock.domain.models.transaction import Transaction


@dataclass(frozen=True)
class CanonicalDataset:
    """Read-only bundle of repositories for deterministic detection."""

    entities: EntityRepository
    providers: ProviderRepository
    accounts: AccountRepository
    transactions: TransactionRepository
    invoices: InvoiceRepository
    payments: PaymentRepository


def transaction_booked_at(tx: Transaction) -> datetime:
    """Resolve a comparable timestamp for temporal detectors.

    Prefer explicit ``booked_at``; otherwise noon UTC on ``transaction_date``.
    """
    if tx.booked_at is not None:
        if tx.booked_at.tzinfo is None:
            return tx.booked_at.replace(tzinfo=timezone.utc)
        return tx.booked_at
    return datetime.combine(tx.transaction_date, time(12, 0), tzinfo=timezone.utc)
