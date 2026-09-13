"""Money-flow adjacency helpers (pure Python; no NetworkX dependency)."""
from __future__ import annotations

from collections import defaultdict

from truelock.detection.dataset import CanonicalDataset, transaction_booked_at
from truelock.domain.models.transaction import Transaction


def build_outbound_index(dataset: CanonicalDataset) -> dict[str, list[Transaction]]:
    index: dict[str, list[Transaction]] = defaultdict(list)
    for tx in dataset.transactions.list():
        index[tx.from_account].append(tx)
    for account in index:
        index[account].sort(key=lambda t: (transaction_booked_at(t), t.id))
    return dict(index)


def build_inbound_index(dataset: CanonicalDataset) -> dict[str, list[Transaction]]:
    index: dict[str, list[Transaction]] = defaultdict(list)
    for tx in dataset.transactions.list():
        index[tx.to_account].append(tx)
    for account in index:
        index[account].sort(key=lambda t: (transaction_booked_at(t), t.id))
    return dict(index)


def entity_for_account(dataset: CanonicalDataset, account_no: str) -> str:
    account = dataset.accounts.get(account_no)
    return account.entity_id if account else account_no
