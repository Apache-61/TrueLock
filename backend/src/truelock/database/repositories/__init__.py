"""Repository layer: read surface and implementations."""
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
from .postgres import PostgresRepositories, validate_database_url

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
    "PostgresRepositories",
    "ProviderRepository",
    "TransactionRepository",
    "validate_database_url",
]
