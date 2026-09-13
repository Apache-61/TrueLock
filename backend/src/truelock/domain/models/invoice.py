"""`Invoice` — a canonical CFDI 4.0 invoice (`domain/schemas/invoice.schema.json`)."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import Field, field_validator

from .base import CanonicalModel


class Invoice(CanonicalModel):
    """One CFDI, reduced to the fields this system reasons about.

    `uuid` is the CFDI's fiscal folio and the join key everything else
    uses: payments reference it, duplicate detection compares against it,
    evidence cites it. It is validated as a real UUID rather than an
    opaque string precisely because a malformed folio would fail to join
    silently -- producing "no duplicates found" rather than an error.
    """

    uuid: str
    provider_rfc: str = Field(min_length=1, description="emisor_rfc")
    receiver_rfc: str = Field(min_length=1, description="receptor_rfc")
    issue_date: date
    amount: float
    version: str = "4.0"
    subtotal: float | None = None
    taxes: float | None = None
    currency: str = "MXN"
    payment_method: str | None = Field(default=None, description="metodo_pago (PUE/PPD)")
    payment_form: str | None = Field(default=None, description="forma_pago")
    cfdi_type: str | None = Field(default=None, description="tipo_comprobante")
    concept: str | None = None

    @field_validator("uuid")
    @classmethod
    def _uuid_is_well_formed(cls, value: str) -> str:
        try:
            UUID(value)
        except (ValueError, AttributeError, TypeError) as error:
            raise ValueError(f"{value!r} is not a well-formed CFDI UUID") from error
        return value

    @field_validator("provider_rfc", "receiver_rfc")
    @classmethod
    def _rfc_is_uppercase(cls, value: str) -> str:
        """RFCs are case-insensitive at source but must be one case here.

        Normalising is safe -- it loses nothing -- and skipping it means
        `ABC010101AAA` and `abc010101aaa` become two different suppliers,
        which quietly defeats every concentration and duplicate rule.
        """
        return value.upper()
