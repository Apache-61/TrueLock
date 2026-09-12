"""Repository layer: the only way the rest of the system reads domain data.

`interfaces.py` declares the read surface as `Protocol`s and imports no
database driver, so every module downstream of TASK-001 can be built and
tested against it before the database exists (TASK-002/-009).
`memory.py` is the implementation that makes that real today; the SQL
implementations satisfy the same protocols later, and callers do not
change.
"""
from __future__ import annotations

from .interfaces import (
    AccountRepository,
    EntityRepository,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)
from .memory import (
    InMemoryAccountRepository,
    InMemoryEntityRepository,
    InMemoryInvoiceRepository,
    InMemoryPaymentRepository,
    InMemoryProviderRepository,
    InMemoryRepositories,
    InMemoryTransactionRepository,
)

__all__ = [
    "AccountRepository",
    "EntityRepository",
    "InMemoryAccountRepository",
    "InMemoryEntityRepository",
    "InMemoryInvoiceRepository",
    "InMemoryPaymentRepository",
    "InMemoryProviderRepository",
    "InMemoryRepositories",
    "InMemoryTransactionRepository",
    "InvoiceRepository",
    "PaymentRepository",
    "ProviderRepository",
    "TransactionRepository",
]
