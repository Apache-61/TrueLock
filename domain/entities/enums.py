"""Enumerations shared by the canonical entities.

Values are copied from `domain/schemas/*.schema.json`, which is the
source of truth. `tests/contract/test_entity_schema_alignment.py`
asserts they still match, rather than trusting this file to be updated
when a schema changes.
"""
from __future__ import annotations

from enum import Enum


class EfosStatus(str, Enum):
    """SAT 69-B listing status of a provider.

    Fiscal evidence, never an automatic fraud label -- a provider on the
    list is a lead to investigate, not a conclusion
    (`domain/enums/efos-status.md`, `docs/regulatory/sat-69b.md`).
    """

    PRESUMED = "PRESUMED"
    DEFINITIVE = "DEFINITIVE"
    INVALIDATED = "INVALIDATED"
    FAVORABLE_JUDGMENT = "FAVORABLE_JUDGMENT"
    #: Not looked up, or the RFC is absent from the snapshot. Distinct
    #: from "not listed": we do not claim knowledge we do not have.
    UNKNOWN = "UNKNOWN"


class EntityType(str, Enum):
    COMPANY = "company"
    INDIVIDUAL = "individual"
