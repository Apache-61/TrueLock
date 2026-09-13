"""Deterministic seed fixtures for the TrueLock end-to-end hackathon demo."""
from __future__ import annotations

from datetime import date
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


def load_demo_scenario(repo: InMemoryRepositories | None = None) -> InMemoryRepositories:
    """Load the single canonical P0 demo scenario into repositories.

    Includes:
    1. One synthetic round-trip fraud cycle:
       - 1,000,000.00 MXN root payment (Company -> Vendor)
       - 920,000.00 MXN rapid downstream transfer (Vendor -> Shell)
       - 740,000.00 MXN circular return (Shell -> Company)
    2. One legitimate control case:
       - Two independent suppliers sharing the same commercial building address (Av. Reforma 222)
       - Distinct RFCs, bank accounts, and independent business purpose (no inter-transfer).
    """
    r = repo if repo is not None else InMemoryRepositories()

    # 1. Root Company
    r.entities.add(
        Entity(
            id="ENT-COMPANY-001",
            rfc="EDE180101AA1",
            entity_type=EntityType.COMPANY,
            name="Empresa Operadora Nacional SA de CV",
        )
    )
    r.accounts.add(
        Account(
            account_no="012180000000000001",
            entity_id="ENT-COMPANY-001",
            bank="BBVA",
        )
    )

    # 2. Vendor (Constructora Primaria)
    r.entities.add(
        Entity(
            id="ENT-VENDOR-001",
            rfc="CPR190515BB2",
            entity_type=EntityType.COMPANY,
            name="Constructora e Infraestructura Primaria SA de CV",
        )
    )
    r.providers.add(
        Provider(
            rfc="CPR190515BB2",
            name="Constructora e Infraestructura Primaria SA de CV",
            efos_status=EfosStatus.UNKNOWN,
            address="Av. Insurgentes Sur 1602, CDMX",
        )
    )
    r.accounts.add(
        Account(
            account_no="012180000000000002",
            entity_id="ENT-VENDOR-001",
            bank="BBVA",
        )
    )

    # 3. Intermediary / Shell Company (Logística Fantasma)
    r.entities.add(
        Entity(
            id="ENT-SHELL-001",
            rfc="LSF200820CC3",
            entity_type=EntityType.COMPANY,
            name="Logística y Enlaces Rápidos Fantasma SA de CV",
        )
    )
    r.providers.add(
        Provider(
            rfc="LSF200820CC3",
            name="Logística y Enlaces Rápidos Fantasma SA de CV",
            efos_status=EfosStatus.DEFINITIVE,  # Contextual SAT 69-B status
            efos_listed_date=date(2025, 11, 10),
            address="Calle Falsa 123, Bodega 4",
        )
    )
    r.accounts.add(
        Account(
            account_no="012180000000000003",
            entity_id="ENT-SHELL-001",
            bank="Banorte",
        )
    )

    # Fraud Invoices & Payments
    r.invoices.add(
        Invoice(
            uuid="11111111-2222-3333-4444-555555555555",
            provider_rfc="CPR190515BB2",
            receiver_rfc="EDE180101AA1",
            issue_date=date(2026, 8, 1),
            amount=1000000.0,
            currency="MXN",
        )
    )
    r.payments.add(
        Payment(
            id="PMT-ROOT-001",
            related_invoice_uuid="11111111-2222-3333-4444-555555555555",
            payment_date=date(2026, 8, 2),
            amount=1000000.0,
            transaction_ids=("TX-ROOT-001",),
        )
    )

    # Fraud Money Flow Transactions
    # TX 1: Root payment out from Company to Vendor
    r.transactions.add(
        Transaction(
            id="TX-ROOT-001",
            from_account="012180000000000001",
            to_account="012180000000000002",
            transaction_date=date(2026, 8, 2),
            amount=1000000.0,
            related_payment_id="PMT-ROOT-001",
        )
    )
    # TX 2: Rapid pass-through to shell (within 2 hours)
    r.transactions.add(
        Transaction(
            id="TX-HOP-001",
            from_account="012180000000000002",
            to_account="012180000000000003",
            transaction_date=date(2026, 8, 2),
            amount=920000.0,
        )
    )
    # TX 3: Return to company account
    r.transactions.add(
        Transaction(
            id="TX-RET-001",
            from_account="012180000000000003",
            to_account="012180000000000001",
            transaction_date=date(2026, 8, 3),
            amount=740000.0,
        )
    )

    # --- 4. Control Group: Legitimate Independent Vendors sharing Commercial Address ---
    r.entities.add(
        Entity(
            id="ENT-VENDOR-CONTROL-A",
            rfc="PCR150310AA1",
            entity_type=EntityType.COMPANY,
            name="Papelería Corporativa Reforma SA",
        )
    )
    r.providers.add(
        Provider(
            rfc="PCR150310AA1",
            name="Papelería Corporativa Reforma SA",
            efos_status=EfosStatus.UNKNOWN,
            address="Av. Reforma 222, Piso 4, CDMX",
        )
    )
    r.accounts.add(
        Account(
            account_no="012180000000000004",
            entity_id="ENT-VENDOR-CONTROL-A",
            bank="Santander",
        )
    )

    r.entities.add(
        Entity(
            id="ENT-VENDOR-CONTROL-B",
            rfc="CRL170822BB2",
            entity_type=EntityType.COMPANY,
            name="Consultoría Reforma Legal SC",
        )
    )
    r.providers.add(
        Provider(
            rfc="CRL170822BB2",
            name="Consultoría Reforma Legal SC",
            efos_status=EfosStatus.UNKNOWN,
            address="Av. Reforma 222, Piso 4, CDMX",
        )
    )
    r.accounts.add(
        Account(
            account_no="012180000000000005",
            entity_id="ENT-VENDOR-CONTROL-B",
            bank="Citibanamex",
        )
    )

    # Legitimate isolated supply payments
    r.transactions.add(
        Transaction(
            id="TX-LEGIT-001",
            from_account="012180000000000001",
            to_account="012180000000000004",
            transaction_date=date(2026, 8, 4),
            amount=15420.0,
        )
    )
    r.transactions.add(
        Transaction(
            id="TX-LEGIT-002",
            from_account="012180000000000001",
            to_account="012180000000000005",
            transaction_date=date(2026, 8, 5),
            amount=38500.0,
        )
    )

    return r
