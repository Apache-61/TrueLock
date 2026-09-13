"""DUPLICATE_INVOICE — same supplier + amount + issue date."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "DUPLICATE_INVOICE"


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    seen: dict[tuple[str, float, object], object] = {}
    signals: list[DetectorSignal] = []
    for inv in sorted(dataset.invoices.list(), key=lambda i: i.uuid):
        key = (inv.provider_rfc, round(inv.amount, 2), inv.issue_date)
        if key in seen:
            orig = seen[key]
            signals.append(
                DetectorSignal(
                    signal_id=f"SIG-DUPINV-{orig.uuid}-{inv.uuid}",
                    detector_id=DETECTOR_ID,
                    entity_id=inv.provider_rfc,
                    claim=(
                        f"Duplicate invoice pattern: provider {inv.provider_rfc} "
                        f"issued {inv.amount:,.2f} MXN twice on {inv.issue_date.isoformat()}."
                    ),
                    source_ids=[orig.uuid, inv.uuid],
                )
            )
        else:
            seen[key] = inv
    return sorted(signals, key=lambda s: s.signal_id)
