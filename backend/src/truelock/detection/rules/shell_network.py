"""SHELL_NETWORK — multi-factor shell clustering (not address alone)."""
from __future__ import annotations

from collections import defaultdict

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.graph import entity_for_account
from truelock.detection.signals import DetectorSignal
from truelock.domain.models.enums import EfosStatus

DETECTOR_ID = "SHELL_NETWORK"


def detect(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Require at least two corroborating factors among address, phone, fund-link, EFOS.

    Shared commercial address alone must NOT fire (negative control case).
    """
    providers = list(dataset.providers.list())
    by_address: dict[str, list] = defaultdict(list)
    by_phone: dict[str, list] = defaultdict(list)
    for provider in providers:
        if provider.address:
            by_address[_norm(provider.address)].append(provider)
        if provider.phone:
            by_phone[_norm(provider.phone)].append(provider)

    fund_links = _entity_fund_links(dataset)
    signals: list[DetectorSignal] = []
    emitted: set[frozenset[str]] = set()

    for address, group in by_address.items():
        if len(group) < 2:
            continue
        rfcs = sorted({p.rfc for p in group})
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                factors = ["shared_address"]
                if left.phone and right.phone and _norm(left.phone) == _norm(right.phone):
                    factors.append("shared_phone")
                if frozenset({left.rfc, right.rfc}) in fund_links:
                    factors.append("fund_link")
                listed = {
                    p.rfc
                    for p in (left, right)
                    if p.efos_status
                    in {
                        EfosStatus.PRESUMED,
                        EfosStatus.DEFINITIVE,
                        EfosStatus.INVALIDATED,
                    }
                }
                if listed:
                    factors.append("efos_listing")
                if len(factors) < 2:
                    continue
                pair = frozenset({left.rfc, right.rfc})
                if pair in emitted:
                    continue
                emitted.add(pair)
                signals.append(
                    DetectorSignal(
                        signal_id=f"SIG-SHELL-{left.rfc}-{right.rfc}",
                        detector_id=DETECTOR_ID,
                        entity_id=left.rfc,
                        claim=(
                            f"Shell-like network factors between {left.rfc} and "
                            f"{right.rfc}: {', '.join(factors)}."
                        ),
                        source_ids=sorted(pair),
                    )
                )

    # Phone-only pairs that also share fund links (no shared address)
    for phone, group in by_phone.items():
        if len(group) < 2:
            continue
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                pair = frozenset({left.rfc, right.rfc})
                if pair in emitted:
                    continue
                if pair not in fund_links:
                    continue
                emitted.add(pair)
                signals.append(
                    DetectorSignal(
                        signal_id=f"SIG-SHELL-{left.rfc}-{right.rfc}",
                        detector_id=DETECTOR_ID,
                        entity_id=left.rfc,
                        claim=(
                            f"Shell-like network factors between {left.rfc} and "
                            f"{right.rfc}: shared_phone, fund_link."
                        ),
                        source_ids=sorted(pair),
                    )
                )

    return sorted(signals, key=lambda s: s.signal_id)


def _norm(value: str) -> str:
    return " ".join(value.upper().split())


def _entity_fund_links(dataset: CanonicalDataset) -> set[frozenset[str]]:
    links: set[frozenset[str]] = set()
    for tx in dataset.transactions.list():
        src = entity_for_account(dataset, tx.from_account)
        dst = entity_for_account(dataset, tx.to_account)
        src_ent = dataset.entities.get(src)
        dst_ent = dataset.entities.get(dst)
        src_rfc = src_ent.rfc if src_ent else None
        dst_rfc = dst_ent.rfc if dst_ent else None
        if src_rfc and dst_rfc and src_rfc != dst_rfc:
            links.add(frozenset({src_rfc, dst_rfc}))
    return links
