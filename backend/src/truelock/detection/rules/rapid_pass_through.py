"""RAPID_PASS_THROUGH / DET-RAPID-PASS-THROUGH — amount + temporal window."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset, transaction_booked_at
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "DET-RAPID-PASS-THROUGH"
MIN_RATIO = 0.75
MAX_RATIO = 1.05
WINDOW_HOURS = 24.0


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    inbound: dict[str, list] = {}
    outbound: dict[str, list] = {}
    for tx in dataset.transactions.list():
        inbound.setdefault(tx.to_account, []).append(tx)
        outbound.setdefault(tx.from_account, []).append(tx)

    signals: list[DetectorSignal] = []
    for account, in_txs in sorted(inbound.items()):
        for in_tx in in_txs:
            in_at = transaction_booked_at(in_tx)
            for out_tx in outbound.get(account, []):
                out_at = transaction_booked_at(out_tx)
                if out_at <= in_at:
                    continue
                hours = (out_at - in_at).total_seconds() / 3600.0
                if hours > WINDOW_HOURS:
                    continue
                if not (in_tx.amount * MIN_RATIO <= out_tx.amount <= in_tx.amount * MAX_RATIO):
                    continue
                signals.append(
                    DetectorSignal(
                        signal_id=f"SIG-PASS-{in_tx.id}-{out_tx.id}",
                        detector_id=DETECTOR_ID,
                        entity_id=account,
                        claim=(
                            f"Rapid pass-through in account {account}: inbound "
                            f"{in_tx.amount:,.2f} MXN followed by outbound "
                            f"{out_tx.amount:,.2f} MXN within {hours:.1f}h."
                        ),
                        source_ids=[in_tx.id, out_tx.id],
                    )
                )
    return sorted(signals, key=lambda s: s.signal_id)
