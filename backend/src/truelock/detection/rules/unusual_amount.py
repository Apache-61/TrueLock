"""UNUSUAL_AMOUNT — robust median/MAD outlier on supplier invoice totals."""
from __future__ import annotations

import statistics

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "UNUSUAL_AMOUNT"
MIN_SAMPLES = 3
MAD_MULTIPLIER = 3.5


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    by_provider: dict[str, list] = {}
    for inv in dataset.invoices.list():
        by_provider.setdefault(inv.provider_rfc, []).append(inv)

    signals: list[DetectorSignal] = []
    for rfc, invoices in sorted(by_provider.items()):
        amounts = [inv.amount for inv in invoices]
        if len(amounts) < MIN_SAMPLES:
            # Fall back to global peer comparison when local history is thin
            peer_amounts = [i.amount for i in dataset.invoices.list()]
            if len(peer_amounts) < MIN_SAMPLES:
                continue
            baseline = peer_amounts
        else:
            baseline = amounts

        median = statistics.median(baseline)
        deviations = [abs(a - median) for a in baseline]
        mad = statistics.median(deviations) or (median * 0.1 if median else 1.0)
        for inv in invoices:
            if mad <= 0:
                continue
            score = abs(inv.amount - median) / mad
            if score < MAD_MULTIPLIER:
                continue
            # Only flag high outliers (not unusually small)
            if inv.amount <= median:
                continue
            signals.append(
                DetectorSignal(
                    signal_id=f"SIG-AMT-{inv.uuid}",
                    detector_id=DETECTOR_ID,
                    entity_id=rfc,
                    claim=(
                        f"Unusual amount {inv.amount:,.2f} MXN for provider {rfc} "
                        f"(median {median:,.2f}, MAD z≈{score:.1f})."
                    ),
                    source_ids=[inv.uuid],
                )
            )
    return sorted(signals, key=lambda s: s.signal_id)
