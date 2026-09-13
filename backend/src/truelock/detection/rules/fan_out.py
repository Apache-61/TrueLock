"""FAN_OUT — many distinct destinations from one account."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.graph import build_outbound_index
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "FAN_OUT"
MIN_DESTINATIONS = 3
MIN_TOTAL = 50_000.0


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    outbound = build_outbound_index(dataset)
    signals: list[DetectorSignal] = []
    for account, txs in sorted(outbound.items()):
        destinations = {tx.to_account for tx in txs}
        total = sum(tx.amount for tx in txs)
        if len(destinations) < MIN_DESTINATIONS or total < MIN_TOTAL:
            continue
        signals.append(
            DetectorSignal(
                signal_id=f"SIG-FANOUT-{account}",
                detector_id=DETECTOR_ID,
                entity_id=account,
                claim=(
                    f"Fan-out: account {account} sent {total:,.2f} MXN to "
                    f"{len(destinations)} distinct destinations."
                ),
                source_ids=sorted(tx.id for tx in txs),
            )
        )
    return sorted(signals, key=lambda s: s.signal_id)
