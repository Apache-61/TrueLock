"""DUPLICATE_PAYMENT / DET-DUPLICATE-PAYMENT."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "DET-DUPLICATE-PAYMENT"


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    seen: dict[tuple[str, float], object] = {}
    signals: list[DetectorSignal] = []
    for payment in sorted(dataset.payments.list(), key=lambda p: p.id):
        key = (payment.related_invoice_uuid, round(payment.amount, 2))
        if key in seen:
            orig = seen[key]
            signals.append(
                DetectorSignal(
                    signal_id=f"SIG-DUP-{orig.id}-{payment.id}",
                    detector_id=DETECTOR_ID,
                    entity_id=payment.related_invoice_uuid,
                    claim=(
                        f"Duplicate payment of {payment.amount:,.2f} MXN for "
                        f"invoice {payment.related_invoice_uuid}."
                    ),
                    source_ids=[orig.id, payment.id],
                )
            )
        else:
            seen[key] = payment
    return sorted(signals, key=lambda s: s.signal_id)
