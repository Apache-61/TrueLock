"""INVOICE_PAYMENT_MISMATCH — payment totals vs invoice amount."""
from __future__ import annotations

from collections import defaultdict

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "INVOICE_PAYMENT_MISMATCH"
TOLERANCE = 0.01  # MXN


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    payments_by_invoice: dict[str, list] = defaultdict(list)
    for payment in dataset.payments.list():
        payments_by_invoice[payment.related_invoice_uuid].append(payment)

    signals: list[DetectorSignal] = []
    for invoice in sorted(dataset.invoices.list(), key=lambda i: i.uuid):
        payments = payments_by_invoice.get(invoice.uuid, [])
        if not payments:
            continue
        paid = sum(p.amount for p in payments)
        if abs(paid - invoice.amount) <= TOLERANCE:
            continue
        signals.append(
            DetectorSignal(
                signal_id=f"SIG-MISMATCH-{invoice.uuid}",
                detector_id=DETECTOR_ID,
                entity_id=invoice.provider_rfc,
                claim=(
                    f"Invoice-payment mismatch on {invoice.uuid}: invoice "
                    f"{invoice.amount:,.2f} MXN vs payments {paid:,.2f} MXN."
                ),
                source_ids=[invoice.uuid, *[p.id for p in payments]],
            )
        )
    return sorted(signals, key=lambda s: s.signal_id)
