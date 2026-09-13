"""`Account` — a bank account (`domain/schemas/account.schema.json`)."""
from __future__ import annotations

from pydantic import Field

from .base import CanonicalModel


class Account(CanonicalModel):
    """A bank account belonging to an entity: a node in the money-flow graph."""

    account_no: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    bank: str | None = None
