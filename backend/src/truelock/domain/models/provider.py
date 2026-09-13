"""`Provider` — a supplier, with fiscal status (`domain/schemas/provider.schema.json`)."""
from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from .base import CanonicalModel
from .enums import EfosStatus


class Provider(CanonicalModel):
    """An RFC-identified supplier, including its SAT 69-B/EFOS status.

    `efos_status` is fiscal evidence, not a verdict. A provider listed as
    DEFINITIVE is a strong lead; it is still the investigation's job to
    show that *these* invoices are the problem
    (`domain/enums/efos-status.md`, ADR-0002).
    """

    rfc: str = Field(min_length=1)
    name: str = Field(min_length=1)
    efos_status: EfosStatus
    registration_date: date | None = None
    address: str | None = None
    phone: str | None = None
    efos_listed_date: date | None = None

    @model_validator(mode="after")
    def _listed_date_requires_a_listing(self) -> "Provider":
        """A listing date without a listing is a contradiction.

        Caught here rather than left to a detector: a record that says
        both "never listed" and "listed on this date" cannot be reasoned
        about, and whichever half a later rule happens to read, the other
        half silently becomes a lie.
        """
        listed = self.efos_status in (
            EfosStatus.PRESUMED,
            EfosStatus.DEFINITIVE,
            EfosStatus.INVALIDATED,
            EfosStatus.FAVORABLE_JUDGMENT,
        )
        if self.efos_listed_date is not None and not listed:
            raise ValueError(
                f"efos_listed_date is set but efos_status is {self.efos_status.value}; "
                "a listing date requires a listing status"
            )
        return self
