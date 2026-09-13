"""`Entity` — any legal or natural person (`domain/schemas/entity.schema.json`)."""
from __future__ import annotations

from pydantic import Field

from .base import CanonicalModel
from .enums import EntityType


class Entity(CanonicalModel):
    """A company or individual that can hold an account or be a party to an invoice."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    entity_type: EntityType
    #: Nullable: not every individual in a dataset has a known RFC, and
    #: inventing one would create a false join key between records.
    rfc: str | None = None
