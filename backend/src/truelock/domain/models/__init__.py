"""Canonical domain entities and investigation models."""
from __future__ import annotations

from .account import Account
from .base import CanonicalModel, EntityValidationError
from .entity import Entity
from .enums import EfosStatus, EntityType
from .investigation import (
    Case,
    Evidence,
    EvidenceStrength,
    EvidenceType,
    Exposure,
    Finding,
    Hypothesis,
    InvestigationStep,
    Lead,
    LeadStatus,
    Outcome,
    Signal,
    StepDecision,
)
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
    "Case",
    "EfosStatus",
    "Entity",
    "EntityType",
    "EntityValidationError",
    "Evidence",
    "EvidenceStrength",
    "EvidenceType",
    "Exposure",
    "Finding",
    "Hypothesis",
    "InvestigationStep",
    "Invoice",
    "Lead",
    "LeadStatus",
    "Outcome",
    "Payment",
    "Provider",
    "Signal",
    "StepDecision",
    "Transaction",
]
