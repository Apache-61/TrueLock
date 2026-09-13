"""Hidden fraud scenarios for judge-controlled demo injection.

These patterns are deliberately absent from the default ``demo_scenario``
until ``POST /demo/inject-fraud`` runs. Answer keys live under
``data/answer_keys/`` and are never exposed to the agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from truelock.database.repositories.memory import InMemoryRepositories
from truelock.domain.models import (
    Account,
    Entity,
    EntityType,
    EfosStatus,
    Invoice,
    Payment,
    Provider,
    Transaction,
)


def _at(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@dataclass(frozen=True)
class InjectionScenario:
    scenario_id: str
    description: str
    primary_entity_id: str


def apply_hidden_pass_through(repo: InMemoryRepositories) -> InjectionScenario:
    """Inject a compact pass-through the detectors can pick up immediately."""
    scenario = InjectionScenario(
        scenario_id="hidden_pass_through",
        description="550k MXN to a new opaque vendor with 91% rapid outbound transfer.",
        primary_entity_id="ENT-HIDDEN-VENDOR-001",
    )
    if repo.entities.get("ENT-HIDDEN-VENDOR-001"):
        return scenario

    repo.entities.add(
        Entity(
            id="ENT-HIDDEN-VENDOR-001",
            rfc="SOV240101AA1",
            entity_type=EntityType.COMPANY,
            name="Servicios Opacos del Centro SA de CV",
        )
    )
    repo.entities.add(
        Entity(
            id="ENT-HIDDEN-SHELL-001",
            rfc="ESC240215BB2",
            entity_type=EntityType.COMPANY,
            name="Enlace Rápido de Capital SC",
        )
    )
    repo.providers.add(
        Provider(
            rfc="SOV240101AA1",
            name="Servicios Opacos del Centro SA de CV",
            efos_status=EfosStatus.PRESUMED,
            address="Calle Oculta 99, CDMX",
        )
    )
    repo.providers.add(
        Provider(
            rfc="ESC240215BB2",
            name="Enlace Rápido de Capital SC",
            efos_status=EfosStatus.DEFINITIVE,
            address="Bodega 7, Zona Industrial",
        )
    )
    repo.accounts.add(
        Account(account_no="012180000000000091", entity_id="ENT-HIDDEN-VENDOR-001", bank="BBVA")
    )
    repo.accounts.add(
        Account(account_no="012180000000000092", entity_id="ENT-HIDDEN-SHELL-001", bank="Banorte")
    )
    repo.invoices.add(
        Invoice(
            uuid="99999999-8888-7777-6666-555555555555",
            provider_rfc="SOV240101AA1",
            receiver_rfc="EDE180101AA1",
            issue_date=date(2026, 9, 1),
            amount=550000.0,
            currency="MXN",
        )
    )
    repo.payments.add(
        Payment(
            id="PMT-HIDDEN-001",
            related_invoice_uuid="99999999-8888-7777-6666-555555555555",
            payment_date=date(2026, 9, 2),
            amount=550000.0,
            transaction_ids=("TX-HIDDEN-ROOT-001",),
        )
    )
    repo.transactions.add(
        Transaction(
            id="TX-HIDDEN-ROOT-001",
            from_account="012180000000000001",
            to_account="012180000000000091",
            transaction_date=date(2026, 9, 2),
            booked_at=_at(2026, 9, 2, 10, 0),
            amount=550000.0,
            related_payment_id="PMT-HIDDEN-001",
        )
    )
    repo.transactions.add(
        Transaction(
            id="TX-HIDDEN-HOP-001",
            from_account="012180000000000091",
            to_account="012180000000000092",
            transaction_date=date(2026, 9, 2),
            booked_at=_at(2026, 9, 2, 11, 0),
            amount=500500.0,
        )
    )
    return scenario


def apply_hidden_duplicate_payment(repo: InMemoryRepositories) -> InjectionScenario:
    """Inject a duplicate payment against an existing invoice UUID."""
    scenario = InjectionScenario(
        scenario_id="hidden_duplicate_payment",
        description="Second full payment for the canonical root invoice UUID.",
        primary_entity_id="ENT-VENDOR-001",
    )
    if repo.transactions.get("TX-HIDDEN-DUP-001"):
        return scenario

    repo.payments.add(
        Payment(
            id="PMT-HIDDEN-DUP-001",
            related_invoice_uuid="11111111-2222-3333-4444-555555555555",
            payment_date=date(2026, 9, 3),
            amount=1000000.0,
            transaction_ids=("TX-HIDDEN-DUP-001",),
        )
    )
    repo.transactions.add(
        Transaction(
            id="TX-HIDDEN-DUP-001",
            from_account="012180000000000001",
            to_account="012180000000000002",
            transaction_date=date(2026, 9, 3),
            booked_at=_at(2026, 9, 3, 14, 0),
            amount=1000000.0,
            related_payment_id="PMT-HIDDEN-DUP-001",
        )
    )
    return scenario


SCENARIOS: dict[str, callable[[InMemoryRepositories], InjectionScenario]] = {
    "hidden_pass_through": apply_hidden_pass_through,
    "hidden_duplicate_payment": apply_hidden_duplicate_payment,
}
