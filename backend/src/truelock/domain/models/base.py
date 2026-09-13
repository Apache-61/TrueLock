"""The validation stance every canonical entity shares.

One rule, and it is the reason this file exists rather than each model
configuring itself: **a record we do not understand is rejected, not
repaired.** `SECURITY.md` and TASK-001's acceptance criteria both say so,
and the failure it prevents is specific -- a forensic conclusion resting
on a field that was silently coerced, defaulted, or dropped during
ingestion is worse than no conclusion, because it looks equally
confident.

Concretely:

* `extra="forbid"` -- an unexpected field is an error. A CFDI with a
  field we have never seen may be a newer version, a different variant,
  or a forgery; none of those should be quietly ingested minus the field
  nobody read.
* `strict=False` with explicit types -- ISO date strings parse into
  `date`, which is what makes the round trip through JSON work, but a
  non-date string still fails rather than becoming today.
* `frozen=True` -- an entity is a record of what a source said. Code that
  wants to change it is making a new record, and should say so.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError


class EntityValidationError(ValueError):
    """A record did not match its contract, with the reason preserved.

    Wraps pydantic's `ValidationError` so callers -- ingestion in
    particular -- can catch one exception type without importing
    pydantic, and so the message names the entity that failed rather
    than a bare model class.
    """

    def __init__(self, entity: str, error: ValidationError) -> None:
        self.entity = entity
        self.errors = error.errors()
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or '<record>'}: {item['msg']}"
            for item in self.errors
        )
        super().__init__(f"{entity} is not valid: {details}")


class CanonicalModel(BaseModel):
    """Base for every entity that mirrors a file in `domain/schemas/`."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        use_enum_values=False,
        str_strip_whitespace=True,
    )

    @classmethod
    def parse(cls, record: dict) -> "CanonicalModel":
        """Build from a raw dict, raising `EntityValidationError` on any problem."""
        try:
            return cls.model_validate(record)
        except ValidationError as error:
            raise EntityValidationError(cls.__name__, error) from error

    def to_dict(self) -> dict:
        """JSON-shaped dict: dates as ISO strings, enums as their values.

        This is the form that round-trips -- `Entity.parse(e.to_dict())`
        reproduces `e` exactly (TASK-001 acceptance criterion), and it is
        what the repositories and the API serialise.
        """
        return self.model_dump(mode="json", exclude_none=True)
