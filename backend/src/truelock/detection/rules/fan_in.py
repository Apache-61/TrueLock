"""FAN_IN — many distinct origins into one account."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.graph import build_inbound_index
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "FAN_IN"
MIN_ORIGINS = 3
MIN_TOTAL = 50_000.0


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    inbound = build_inbound_index(dataset)
    signals: list[DetectorSignal] = []
    for account, txs in sorted(inbound.items()):
        origins = {tx.from_account for tx in txs}
        total = sum(tx.amount for tx in txs)
        if len(origins) < MIN_ORIGINS or total < MIN_TOTAL:
            continue
        signals.append(
            DetectorSignal(
                signal_id=f"SIG-FANIN-{account}",
                detector_id=DETECTOR_ID,
                entity_id=account,
                claim=(
                    f"Fan-in: account {account} received {total:,.2f} MXN from "
                    f"{len(origins)} distinct origins."
                ),
                source_ids=sorted(tx.id for tx in txs),
            )
        )
    return sorted(signals, key=lambda s: s.signal_id)
