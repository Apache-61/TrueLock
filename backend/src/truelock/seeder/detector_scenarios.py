"""Synthetic positive/negative datasets for detector regression (Fase 5)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from truelock.database.repositories.memory import InMemoryRepositories
from truelock.domain.models import (
    Account,
    EfosStatus,
    Entity,
    EntityType,
    Invoice,
    Payment,
    Provider,
    Transaction,
)


def _at(y: int, m: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def scenario_duplicate_invoice(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.entities.add(Entity(id="ENT-A", rfc="AAA010101AAA", entity_type=EntityType.COMPANY, name="A"))
    r.providers.add(Provider(rfc="AAA010101AAA", name="A", efos_status=EfosStatus.UNKNOWN))
    r.invoices.add(
        Invoice(
            uuid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
            provider_rfc="AAA010101AAA",
            receiver_rfc="BBB010101BBB",
            issue_date=date(2026, 1, 10),
            amount=250000.0,
        )
    )
    r.invoices.add(
        Invoice(
            uuid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
            provider_rfc="AAA010101AAA",
            receiver_rfc="BBB010101BBB",
            issue_date=date(2026, 1, 10) if positive else date(2026, 1, 11),
            amount=250000.0 if positive else 251000.0,
        )
    )
    return r


def scenario_unusual_amount(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.providers.add(Provider(rfc="CCC010101CCC", name="C", efos_status=EfosStatus.UNKNOWN))
    for i, amount in enumerate([10000.0, 11000.0, 10500.0, 500000.0 if positive else 12000.0]):
        r.invoices.add(
            Invoice(
                uuid=f"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb{i:02d}",
                provider_rfc="CCC010101CCC",
                receiver_rfc="DDD010101DDD",
                issue_date=date(2026, 2, i + 1),
                amount=amount,
            )
        )
    return r


def scenario_invoice_payment_mismatch(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.providers.add(Provider(rfc="EEE010101EEE", name="E", efos_status=EfosStatus.UNKNOWN))
    inv = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    r.invoices.add(
        Invoice(
            uuid=inv,
            provider_rfc="EEE010101EEE",
            receiver_rfc="FFF010101FFF",
            issue_date=date(2026, 3, 1),
            amount=100000.0,
        )
    )
    r.payments.add(
        Payment(
            id="PMT-MIS-001",
            related_invoice_uuid=inv,
            payment_date=date(2026, 3, 5),
            amount=100000.0 if not positive else 70000.0,
        )
    )
    return r


def scenario_fan_in(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.entities.add(Entity(id="ENT-HUB", rfc="HUB010101AAA", entity_type=EntityType.COMPANY, name="Hub"))
    r.accounts.add(Account(account_no="ACC-HUB", entity_id="ENT-HUB", bank="BBVA"))
    origins = ["ACC-O1", "ACC-O2", "ACC-O3"] if positive else ["ACC-O1", "ACC-O2"]
    for i, acc in enumerate(origins):
        r.entities.add(
            Entity(id=f"ENT-O{i}", rfc=f"OOO01010{i}AAA", entity_type=EntityType.COMPANY, name=f"O{i}")
        )
        r.accounts.add(Account(account_no=acc, entity_id=f"ENT-O{i}", bank="BBVA"))
        r.transactions.add(
            Transaction(
                id=f"TX-FANIN-{i}",
                from_account=acc,
                to_account="ACC-HUB",
                transaction_date=date(2026, 4, 1),
                booked_at=_at(2026, 4, 1, 10 + i),
                amount=40000.0,
            )
        )
    return r


def scenario_fan_out(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.entities.add(Entity(id="ENT-SRC", rfc="SRC010101AAA", entity_type=EntityType.COMPANY, name="Src"))
    r.accounts.add(Account(account_no="ACC-SRC", entity_id="ENT-SRC", bank="BBVA"))
    dests = ["ACC-D1", "ACC-D2", "ACC-D3"] if positive else ["ACC-D1", "ACC-D2"]
    for i, acc in enumerate(dests):
        r.entities.add(
            Entity(id=f"ENT-D{i}", rfc=f"DDD01010{i}BBB", entity_type=EntityType.COMPANY, name=f"D{i}")
        )
        r.accounts.add(Account(account_no=acc, entity_id=f"ENT-D{i}", bank="BBVA"))
        r.transactions.add(
            Transaction(
                id=f"TX-FANOUT-{i}",
                from_account="ACC-SRC",
                to_account=acc,
                transaction_date=date(2026, 4, 2),
                booked_at=_at(2026, 4, 2, 10 + i),
                amount=40000.0,
            )
        )
    return r


def scenario_efos_negative_no_accusation() -> InMemoryRepositories:
    """Listed EFOS provider with no corroborating money pattern — must stay low risk."""
    r = InMemoryRepositories()
    r.providers.add(
        Provider(
            rfc="GGG010101GGG",
            name="Listed but quiet",
            efos_status=EfosStatus.DEFINITIVE,
            efos_listed_date=date(2025, 1, 1),
            address="Calle Quiet 1",
        )
    )
    r.invoices.add(
        Invoice(
            uuid="dddddddd-dddd-dddd-dddd-dddddddddddd",
            provider_rfc="GGG010101GGG",
            receiver_rfc="HHH010101HHH",
            issue_date=date(2026, 5, 1),
            amount=5000.0,
        )
    )
    return r


def scenario_pass_through_temporal(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.accounts.add(Account(account_no="ACC-PT", entity_id="ENT-PT", bank="BBVA"))
    r.accounts.add(Account(account_no="ACC-IN", entity_id="ENT-IN", bank="BBVA"))
    r.accounts.add(Account(account_no="ACC-OUT", entity_id="ENT-OUT", bank="BBVA"))
    r.transactions.add(
        Transaction(
            id="TX-PT-IN",
            from_account="ACC-IN",
            to_account="ACC-PT",
            transaction_date=date(2026, 6, 1),
            booked_at=_at(2026, 6, 1, 9, 0),
            amount=200000.0,
        )
    )
    # Positive: 2h later. Negative: 48h later (outside window) OR reverse order
    if positive:
        out_at = _at(2026, 6, 1, 11, 0)
        out_date = date(2026, 6, 1)
    else:
        out_at = _at(2026, 6, 3, 11, 0)
        out_date = date(2026, 6, 3)
    r.transactions.add(
        Transaction(
            id="TX-PT-OUT",
            from_account="ACC-PT",
            to_account="ACC-OUT",
            transaction_date=out_date,
            booked_at=out_at,
            amount=180000.0,
        )
    )
    return r


def scenario_cycle_dedup() -> InMemoryRepositories:
    """Three-hop cycle that must produce exactly one CIRCULAR_FLOW lead."""
    r = InMemoryRepositories()
    for i, acc in enumerate(["A1", "A2", "A3"]):
        r.entities.add(
            Entity(id=f"E{i}", rfc=f"CYC01010{i}AAA", entity_type=EntityType.COMPANY, name=f"C{i}")
        )
        r.accounts.add(Account(account_no=acc, entity_id=f"E{i}", bank="BBVA"))
    r.transactions.add(
        Transaction(
            id="TX-C1",
            from_account="A1",
            to_account="A2",
            transaction_date=date(2026, 7, 1),
            booked_at=_at(2026, 7, 1, 9),
            amount=100000.0,
            related_payment_id="PMT-C1",
        )
    )
    r.transactions.add(
        Transaction(
            id="TX-C2",
            from_account="A2",
            to_account="A3",
            transaction_date=date(2026, 7, 1),
            booked_at=_at(2026, 7, 1, 11),
            amount=90000.0,
        )
    )
    r.transactions.add(
        Transaction(
            id="TX-C3",
            from_account="A3",
            to_account="A1",
            transaction_date=date(2026, 7, 1),
            booked_at=_at(2026, 7, 1, 15),
            amount=80000.0,
        )
    )
    return r


def scenario_supplier_concentration(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.entities.add(
        Entity(id="ENT-PAYER", rfc="PAY010101AAA", entity_type=EntityType.COMPANY, name="Payer")
    )
    r.accounts.add(Account(account_no="ACC-PAY", entity_id="ENT-PAYER", bank="BBVA"))
    destinations = [
        ("ENT-TOP", "TOP010101AAA", "ACC-TOP", 800000.0 if positive else 400000.0),
        ("ENT-A", "AAA010101ZZZ", "ACC-A", 100000.0),
        ("ENT-B", "BBB010101ZZZ", "ACC-B", 100000.0),
    ]
    for entity_id, rfc, acct, amount in destinations:
        r.entities.add(Entity(id=entity_id, rfc=rfc, entity_type=EntityType.COMPANY, name=rfc))
        r.accounts.add(Account(account_no=acct, entity_id=entity_id, bank="BBVA"))
        r.transactions.add(
            Transaction(
                id=f"TX-CONC-{acct}",
                from_account="ACC-PAY",
                to_account=acct,
                transaction_date=date(2026, 8, 1),
                booked_at=_at(2026, 8, 1, 10),
                amount=amount,
            )
        )
    return r


def scenario_shell_network(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.providers.add(
        Provider(
            rfc="SHL010101AAA",
            name="Shell A",
            efos_status=EfosStatus.DEFINITIVE if positive else EfosStatus.UNKNOWN,
            efos_listed_date=date(2025, 1, 1) if positive else None,
            address="Calle Compartida 1",
            phone="555-1000",
        )
    )
    r.providers.add(
        Provider(
            rfc="SHL010101BBB",
            name="Shell B",
            efos_status=EfosStatus.UNKNOWN,
            address="Calle Compartida 1",
            phone="555-1000" if positive else "555-2000",
        )
    )
    r.entities.add(
        Entity(id="ENT-SA", rfc="SHL010101AAA", entity_type=EntityType.COMPANY, name="Shell A")
    )
    r.entities.add(
        Entity(id="ENT-SB", rfc="SHL010101BBB", entity_type=EntityType.COMPANY, name="Shell B")
    )
    r.accounts.add(Account(account_no="ACC-SA", entity_id="ENT-SA", bank="BBVA"))
    r.accounts.add(Account(account_no="ACC-SB", entity_id="ENT-SB", bank="BBVA"))
    if positive:
        r.transactions.add(
            Transaction(
                id="TX-SHELL-LINK",
                from_account="ACC-SA",
                to_account="ACC-SB",
                transaction_date=date(2026, 8, 10),
                booked_at=_at(2026, 8, 10, 12),
                amount=25000.0,
            )
        )
    return r


def scenario_unusual_timing(*, positive: bool) -> InMemoryRepositories:
    r = InMemoryRepositories()
    r.providers.add(Provider(rfc="TIM010101AAA", name="Timer", efos_status=EfosStatus.UNKNOWN))
    inv = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    issue = date(2026, 8, 20)
    pay_date = issue if positive else date(2026, 8, 25)
    r.invoices.add(
        Invoice(
            uuid=inv,
            provider_rfc="TIM010101AAA",
            receiver_rfc="REC010101AAA",
            issue_date=issue,
            amount=250000.0,
        )
    )
    r.payments.add(
        Payment(
            id="PMT-TIME-001",
            related_invoice_uuid=inv,
            payment_date=pay_date,
            amount=250000.0,
        )
    )
    return r
