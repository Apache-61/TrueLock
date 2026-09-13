"""UNUSUAL_TIMING — same-day large settlement or overnight hops."""
from __future__ import annotations

from truelock.detection.dataset import CanonicalDataset, transaction_booked_at
from truelock.detection.signals import DetectorSignal

DETECTOR_ID = "UNUSUAL_TIMING"
LARGE_AMOUNT = 100_000.0


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    signals: list[DetectorSignal] = []

    invoices = {inv.uuid: inv for inv in dataset.invoices.list()}
    for payment in sorted(dataset.payments.list(), key=lambda p: p.id):
        inv = invoices.get(payment.related_invoice_uuid)
        if not inv:
            continue
        if payment.amount < LARGE_AMOUNT:
            continue
        if payment.payment_date != inv.issue_date:
            continue
        signals.append(
            DetectorSignal(
                signal_id=f"SIG-TIME-PAY-{payment.id}",
                detector_id=DETECTOR_ID,
                entity_id=inv.provider_rfc,
                claim=(
                    f"Unusual timing: invoice {inv.uuid} for {inv.amount:,.2f} MXN "
                    f"settled the same day it was issued."
                ),
                source_ids=[inv.uuid, payment.id],
            )
        )

    # Overnight / sub-6h large hop without invoice link
    txs = sorted(dataset.transactions.list(), key=lambda t: (transaction_booked_at(t), t.id))
    by_account_out: dict[str, list] = {}
    by_account_in: dict[str, list] = {}
    for tx in txs:
        by_account_out.setdefault(tx.from_account, []).append(tx)
        by_account_in.setdefault(tx.to_account, []).append(tx)

    for account, in_txs in by_account_in.items():
        for in_tx in in_txs:
            if in_tx.amount < LARGE_AMOUNT:
                continue
            for out_tx in by_account_out.get(account, []):
                if out_tx.related_payment_id or in_tx.id == out_tx.id:
                    continue
                delta_h = (
                    transaction_booked_at(out_tx) - transaction_booked_at(in_tx)
                ).total_seconds() / 3600.0
                if not (0 < delta_h <= 6):
                    continue
                if out_tx.amount < in_tx.amount * 0.7:
                    continue
                signals.append(
                    DetectorSignal(
                        signal_id=f"SIG-TIME-HOP-{in_tx.id}-{out_tx.id}",
                        detector_id=DETECTOR_ID,
                        entity_id=account,
                        claim=(
                            f"Unusual timing: {in_tx.amount:,.2f} MXN entered "
                            f"{account} and {out_tx.amount:,.2f} MXN left within "
                            f"{delta_h:.1f}h."
                        ),
                        source_ids=[in_tx.id, out_tx.id],
                    )
                )

    # Deduplicate by signal_id
    unique = {s.signal_id: s for s in signals}
    return sorted(unique.values(), key=lambda s: s.signal_id)
