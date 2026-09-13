"""DetectorSignal — atomic deterministic detector output."""
from __future__ import annotations

from pydantic import Field

from truelock.domain.models.base import CanonicalModel


class DetectorSignal(CanonicalModel):
    """Fact emitted by one detector; not a pursue/discard decision.

    Mirrors ``domain/schemas/detector_signal.schema.json``.
    """

    signal_id: str
    detector_id: str
    entity_id: str
    claim: str
    source_ids: list[str] = Field(default_factory=list)
    computed_at: str | None = None
