"""In-memory repositories over canonical records.

Not a toy. This is what lets the tasks downstream of TASK-001 be built
and tested before the database lands (TASK-002/-009): the agent tools,
the detectors and the API can all run against a loaded scenario today,
the same way the frontend shell is built against its mock. When the SQL
implementations arrive they satisfy the same `Protocol`s and the callers
do not change.

It is also the fixture every later test uses, so the query semantics --
ordering, inclusivity, what "no results" means -- are pinned here once
rather than re-decided per module.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from truelock.domain.models import Account, Entity, Invoice, Payment, Provider, Transaction


def _page(items: list, limit: int, offset: int) -> list:
    if limit < 0 or offset < 0:
        raise ValueError("limit and offset must not be negative")
    return items[offset : offset + limit]


@dataclass
class InMemoryProviderRepository:
    providers: dict[str, Provider] = field(default_factory=dict)

    def add(self, provider: Provider) -> None:
        self.providers[provider.rfc] = provider

    def get(self, rfc: str) -> Provider | None:
        return self.providers.get((rfc or "").upper())

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Provider]:
        return _page(sorted(self.providers.values(), key=lambda item: item.rfc), limit, offset)

    def list_by_efos_status(self, status: str) -> list[Provider]:
        wanted = str(getattr(status, "value", status))
        return [
            provider
            for provider in sorted(self.providers.values(), key=lambda item: item.rfc)
            if provider.efos_status.value == wanted
        ]


@dataclass
class InMemoryEntityRepository:
    entities: dict[str, Entity] = field(default_factory=dict)

    def add(self, entity: Entity) -> None:
        self.entities[entity.id] = entity

    def get(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)

    def get_by_rfc(self, rfc: str) -> Entity | None:
        target = (rfc or "").upper()
        for entity in sorted(self.entities.values(), key=lambda item: item.id):
            if entity.rfc and entity.rfc.upper() == target:
                return entity
        return None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Entity]:
        return _page(sorted(self.entities.values(), key=lambda item: item.id), limit, offset)


@dataclass
class InMemoryInvoiceRepository:
    invoices: dict[str, Invoice] = field(default_factory=dict)

    def add(self, invoice: Invoice) -> None:
        self.invoices[invoice.uuid] = invoice

    def get(self, uuid: str) -> Invoice | None:
        return self.invoices.get(uuid)

    def _ordered(self) -> list[Invoice]:
        return sorted(self.invoices.values(), key=lambda item: (item.issue_date, item.uuid))

    def list_by_provider(self, provider_rfc: str) -> list[Invoice]:
        target = (provider_rfc or "").upper()
        return [item for item in self._ordered() if item.provider_rfc == target]

    def list_by_receiver(self, receiver_rfc: str) -> list[Invoice]:
        target = (receiver_rfc or "").upper()
        return [item for item in self._ordered() if item.receiver_rfc == target]

    def list_in_period(self, start: date, end: date) -> list[Invoice]:
        if start > end:
            raise ValueError(f"start {start} is after end {end}")
        return [item for item in self._ordered() if start <= item.issue_date <= end]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Invoice]:
        return _page(self._ordered(), limit, offset)


@dataclass
class InMemoryPaymentRepository:
    payments: dict[str, Payment] = field(default_factory=dict)

    def add(self, payment: Payment) -> None:
        self.payments[payment.id] = payment

    def get(self, payment_id: str) -> Payment | None:
        return self.payments.get(payment_id)

    def _ordered(self) -> list[Payment]:
        return sorted(self.payments.values(), key=lambda item: (item.payment_date, item.id))

    def list_for_invoice(self, invoice_uuid: str) -> list[Payment]:
        return [item for item in self._ordered() if item.related_invoice_uuid == invoice_uuid]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Payment]:
        return _page(self._ordered(), limit, offset)


@dataclass
class InMemoryTransactionRepository:
    transactions: dict[str, Transaction] = field(default_factory=dict)

    def add(self, transaction: Transaction) -> None:
        self.transactions[transaction.id] = transaction

    def get(self, transaction_id: str) -> Transaction | None:
        return self.transactions.get(transaction_id)

    def _ordered(self) -> list[Transaction]:
        return sorted(
            self.transactions.values(), key=lambda item: (item.transaction_date, item.id)
        )

    def list_outgoing(self, account_no: str) -> list[Transaction]:
        return [item for item in self._ordered() if item.from_account == account_no]

    def list_incoming(self, account_no: str) -> list[Transaction]:
        return [item for item in self._ordered() if item.to_account == account_no]

    def list_for_payment(self, payment_id: str) -> list[Transaction]:
        return [item for item in self._ordered() if item.related_payment_id == payment_id]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Transaction]:
        return _page(self._ordered(), limit, offset)


@dataclass
class InMemoryAccountRepository:
    accounts: dict[str, Account] = field(default_factory=dict)

    def add(self, account: Account) -> None:
        self.accounts[account.account_no] = account

    def get(self, account_no: str) -> Account | None:
        return self.accounts.get(account_no)

    def list_for_entity(self, entity_id: str) -> list[Account]:
        return [
            item
            for item in sorted(self.accounts.values(), key=lambda item: item.account_no)
            if item.entity_id == entity_id
        ]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Account]:
        return _page(sorted(self.accounts.values(), key=lambda item: item.account_no), limit, offset)


@dataclass
class InMemoryRepositories:
    """All six, so a caller passes one object around instead of six."""

    providers: InMemoryProviderRepository = field(default_factory=InMemoryProviderRepository)
    entities: InMemoryEntityRepository = field(default_factory=InMemoryEntityRepository)
    invoices: InMemoryInvoiceRepository = field(default_factory=InMemoryInvoiceRepository)
    payments: InMemoryPaymentRepository = field(default_factory=InMemoryPaymentRepository)
    transactions: InMemoryTransactionRepository = field(
        default_factory=InMemoryTransactionRepository
    )
    accounts: InMemoryAccountRepository = field(default_factory=InMemoryAccountRepository)

    def load(self, records: Iterable) -> "InMemoryRepositories":
        """Add a mixed stream of canonical records, dispatching by type."""
        targets = {
            Provider: self.providers,
            Entity: self.entities,
            Invoice: self.invoices,
            Payment: self.payments,
            Transaction: self.transactions,
            Account: self.accounts,
        }
        for record in records:
            target = targets.get(type(record))
            if target is None:
                raise TypeError(f"not a canonical entity: {type(record).__name__}")
            target.add(record)
        return self

    def __len__(self) -> int:
        return sum(
            len(store)
            for store in (
                self.providers.providers,
                self.entities.entities,
                self.invoices.invoices,
                self.payments.payments,
                self.transactions.transactions,
                self.accounts.accounts,
            )
        )
