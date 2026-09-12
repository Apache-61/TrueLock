"""The read surface every other module uses to reach domain data.

These are `Protocol`s, not base classes, and this file imports no
database driver. That is the point of TASK-001's fourth acceptance
criterion: the agent tools (TASK-005), the detection pipeline (TASK-019)
and the API (TASK-032) all depend on *this*, so none of them has to wait
for the database to exist, and none of them can reach around it into SQL.

The methods are the queries the system actually needs, not a generic ORM
surface. A repository that can express any query is a repository whose
cost nobody can reason about -- and these run inside an agent loop that
is charged per call.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from domain.entities import Account, Entity, Invoice, Payment, Provider, Transaction


@runtime_checkable
class ProviderRepository(Protocol):
    def get(self, rfc: str) -> Provider | None: ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Provider]: ...

    def list_by_efos_status(self, status: str) -> list[Provider]: ...


@runtime_checkable
class EntityRepository(Protocol):
    def get(self, entity_id: str) -> Entity | None: ...

    def get_by_rfc(self, rfc: str) -> Entity | None: ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Entity]: ...


@runtime_checkable
class InvoiceRepository(Protocol):
    def get(self, uuid: str) -> Invoice | None: ...

    def list_by_provider(self, provider_rfc: str) -> list[Invoice]: ...

    def list_by_receiver(self, receiver_rfc: str) -> list[Invoice]: ...

    def list_in_period(self, start: date, end: date) -> list[Invoice]:
        """Inclusive of both endpoints. Ordered by issue date."""
        ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Invoice]: ...


@runtime_checkable
class PaymentRepository(Protocol):
    def get(self, payment_id: str) -> Payment | None: ...

    def list_for_invoice(self, invoice_uuid: str) -> list[Payment]: ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Payment]: ...


@runtime_checkable
class TransactionRepository(Protocol):
    def get(self, transaction_id: str) -> Transaction | None: ...

    def list_outgoing(self, account_no: str) -> list[Transaction]:
        """Movements leaving this account, ordered by date. A graph edge query."""
        ...

    def list_incoming(self, account_no: str) -> list[Transaction]: ...

    def list_for_payment(self, payment_id: str) -> list[Transaction]: ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Transaction]: ...


@runtime_checkable
class AccountRepository(Protocol):
    def get(self, account_no: str) -> Account | None: ...

    def list_for_entity(self, entity_id: str) -> list[Account]: ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Account]: ...
