"""CIRCULAR_FLOW / DET-ROUND-TRIP-CYCLE — temporally ordered, deduplicated cycles."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset, transaction_booked_at
from truelock.detection.graph import build_outbound_index, entity_for_account
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "DET-ROUND-TRIP-CYCLE"
DOC_ID = "CIRCULAR_FLOW"
MAX_HOPS = 3


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Emit one signal per unique cycle (frozenset of transaction IDs)."""
    outbound = build_outbound_index(dataset)
    seen_cycles: set[frozenset[str]] = set()
    signals: list[DetectorSignal] = []

    for start_tx in sorted(dataset.transactions.list(), key=lambda t: (transaction_booked_at(t), t.id)):
        _walk(
            start_tx=start_tx,
            path_txs=[start_tx],
            path_accounts=[start_tx.from_account, start_tx.to_account],
            outbound=outbound,
            seen_cycles=seen_cycles,
            signals=signals,
            dataset=dataset,
        )

    return sorted(signals, key=lambda s: s.signal_id)


def _walk(
    *,
    start_tx,
    path_txs,
    path_accounts,
    outbound,
    seen_cycles,
    signals,
    dataset,
) -> None:
    if len(path_txs) > MAX_HOPS:
        return
    current = path_accounts[-1]
    for next_tx in outbound.get(current, []):
        if next_tx in path_txs:
            continue
        if transaction_booked_at(next_tx) < transaction_booked_at(path_txs[-1]):
            continue
        new_accounts = path_accounts + [next_tx.to_account]
        new_txs = path_txs + [next_tx]
        if next_tx.to_account == path_accounts[0] and len(new_txs) >= 2:
            cycle_key = frozenset(tx.id for tx in new_txs)
            if cycle_key in seen_cycles:
                continue
            seen_cycles.add(cycle_key)
            root = _economic_root(new_txs)
            entity_id = entity_for_account(dataset, root.from_account)
            # Prefer account number for demo compatibility when entity missing
            if entity_id == root.from_account or not entity_id:
                entity_id = root.from_account
            # Demo historically used account as entity_id for cycle leads
            entity_id = root.from_account
            tx_ids = [tx.id for tx in new_txs]
            amounts = ", ".join(f"{tx.amount:,.2f}" for tx in new_txs)
            hop_path = " -> ".join(new_accounts)
            signals.append(
                DetectorSignal(
                    signal_id=f"SIG-CYCLE-{'-'.join(sorted(tx_ids))}",
                    detector_id=DETECTOR_ID,
                    entity_id=entity_id,
                    claim=(
                        f"Round-trip cycle detected: {hop_path} "
                        f"moving [{amounts}] MXN with temporal order respected "
                        f"({DOC_ID})."
                    ),
                    source_ids=tx_ids,
                )
            )
            continue
        if len(new_txs) < MAX_HOPS:
            _walk(
                start_tx=start_tx,
                path_txs=new_txs,
                path_accounts=new_accounts,
                outbound=outbound,
                seen_cycles=seen_cycles,
                signals=signals,
                dataset=dataset,
            )


def _economic_root(txs):
    for tx in txs:
        if tx.related_payment_id:
            return tx
    return min(txs, key=lambda t: (transaction_booked_at(t), t.id))
