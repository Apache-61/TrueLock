"""69B_CORRELATION — contextual SAT listing correlated with activity (not a verdict)."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.signals import DetectorSignal
from truelock.domain.models.enums import EfosStatus

DETECTOR_ID = "69B_CORRELATION"
LISTED = {
    EfosStatus.PRESUMED,
    EfosStatus.DEFINITIVE,
    EfosStatus.INVALIDATED,
}


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Emit when a listed RFC also appears as invoice issuer or payment counterparty.

    Weight alone stays below pursue threshold — EFOS is contextual evidence.
    """
    active_rfcs: set[str] = set()
    sources_by_rfc: dict[str, list[str]] = {}
    for inv in dataset.invoices.list():
        active_rfcs.add(inv.provider_rfc)
        sources_by_rfc.setdefault(inv.provider_rfc, []).append(inv.uuid)
    for payment in dataset.payments.list():
        inv = dataset.invoices.get(payment.related_invoice_uuid)
        if inv:
            active_rfcs.add(inv.provider_rfc)
            sources_by_rfc.setdefault(inv.provider_rfc, []).append(payment.id)

    signals: list[DetectorSignal] = []
    for provider in sorted(dataset.providers.list(), key=lambda p: p.rfc):
        if provider.efos_status not in LISTED:
            continue
        if provider.rfc not in active_rfcs:
            continue
        signals.append(
            DetectorSignal(
                signal_id=f"SIG-69B-{provider.rfc}",
                detector_id=DETECTOR_ID,
                entity_id=provider.rfc,
                claim=(
                    f"69-B correlation: provider {provider.rfc} is "
                    f"{provider.efos_status.value} and has invoices/payments in-scope "
                    f"(contextual signal, not a fraud conclusion)."
                ),
                source_ids=sorted(set(sources_by_rfc.get(provider.rfc, [provider.rfc]))),
            )
        )
    return sorted(signals, key=lambda s: s.signal_id)
