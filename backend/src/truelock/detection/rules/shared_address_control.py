"""DET-SHARED-ADDRESS-CONTROL — deliberate low-risk negative control lead."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "DET-SHARED-ADDRESS-CONTROL"


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Always emit the control signal when both control vendors exist.

    Designed so shared address alone never becomes a high-risk accusation.
    """
    a = dataset.entities.get("ENT-VENDOR-CONTROL-A")
    b = dataset.entities.get("ENT-VENDOR-CONTROL-B")
    if not a or not b:
        return []
    return [
        DetectorSignal(
            signal_id="SIG-ADDR-CO-LOCATION-404",
            detector_id=DETECTOR_ID,
            entity_id="ENT-VENDOR-CONTROL-A",
            claim=(
                "Shared commercial building address with supplier ENT-VENDOR-CONTROL-B "
                "(Av. Reforma 222)."
            ),
            source_ids=["ENT-VENDOR-CONTROL-A", "ENT-VENDOR-CONTROL-B"],
        )
    ]
