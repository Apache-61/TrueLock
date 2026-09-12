"""Canonical domain entities — the Python side of `domain/schemas/`.

The JSON Schema files are the source of truth; these mirror them 1:1 and
must not drift. `tests/contract/test_entity_schema_alignment.py` checks
every field, requirement and enum against the schema rather than trusting
that to review.

Two layers of the domain live here:

* **canonical records** — `Entity`, `Provider`, `Invoice`, `Payment`,
  `Transaction`, `Account`: what the source data says.
* the investigation layer (`Lead`, `Evidence`, `InvestigationStep`,
  `Case`) is TASK-008, and lands alongside these.
"""
from __future__ import annotations

from .account import Account
from .base import CanonicalModel, EntityValidationError
from .entity import Entity
from .enums import EfosStatus, EntityType
from .invoice import Invoice
from .payment import Payment
from .provider import Provider
from .transaction import Transaction

#: schema filename stem -> entity class. Used by the contract test and by
#: ingestion to pick a validator by record type.
CANONICAL_ENTITIES: dict[str, type[CanonicalModel]] = {
    "account": Account,
    "entity": Entity,
    "invoice": Invoice,
    "payment": Payment,
    "provider": Provider,
    "transaction": Transaction,
}

__all__ = [
    "Account",
    "CANONICAL_ENTITIES",
    "CanonicalModel",
    "Entity",
    "EntityValidationError",
    "EfosStatus",
    "EntityType",
    "Invoice",
    "Payment",
    "Provider",
    "Transaction",
]
