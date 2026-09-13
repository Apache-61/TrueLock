"""SUPPLIER_CONCENTRATION — one supplier dominates outbound spend."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.graph import entity_for_account
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "SUPPLIER_CONCENTRATION"
CONCENTRATION_RATIO = 0.70
MIN_TOTAL = 100_000.0


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Flag when one destination entity receives >= 70% of a payer's outbound."""
    by_payer: dict[str, list] = {}
    for tx in dataset.transactions.list():
        payer = entity_for_account(dataset, tx.from_account)
        by_payer.setdefault(payer, []).append(tx)

    signals: list[DetectorSignal] = []
    for payer, txs in sorted(by_payer.items()):
        total = sum(tx.amount for tx in txs)
        if total < MIN_TOTAL:
            continue
        by_dest: dict[str, float] = {}
        dest_sources: dict[str, list[str]] = {}
        for tx in txs:
            dest = entity_for_account(dataset, tx.to_account)
            if dest == payer:
                continue
            by_dest[dest] = by_dest.get(dest, 0.0) + tx.amount
            dest_sources.setdefault(dest, []).append(tx.id)
        if not by_dest:
            continue
        top_dest, top_amt = max(by_dest.items(), key=lambda item: item[1])
        ratio = top_amt / total
        if ratio < CONCENTRATION_RATIO:
            continue
        signals.append(
            DetectorSignal(
                signal_id=f"SIG-CONC-{payer}-{top_dest}",
                detector_id=DETECTOR_ID,
                entity_id=top_dest,
                claim=(
                    f"Supplier concentration: {top_dest} received {ratio:.0%} "
                    f"({top_amt:,.2f} of {total:,.2f} MXN) from {payer}."
                ),
                source_ids=sorted(dest_sources[top_dest]),
            )
        )
    return sorted(signals, key=lambda s: s.signal_id)
