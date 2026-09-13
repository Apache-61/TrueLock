"""Seed the TrueLock demo scenario into memory or print fixture summary."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/src is on import path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from truelock.seeder.demo_scenario import load_demo_scenario


def main() -> None:
    print("=== TrueLock Demo Scenario Seeder ===")
    repo = load_demo_scenario()
    entities = repo.entities.list()
    providers = repo.providers.list()
    accounts = repo.accounts.list()
    transactions = repo.transactions.list()
    invoices = repo.invoices.list()
    payments = repo.payments.list()

    print(f"Loaded Entities:     {len(entities)}")
    print(f"Loaded Providers:    {len(providers)}")
    print(f"Loaded Accounts:     {len(accounts)}")
    print(f"Loaded Invoices:     {len(invoices)}")
    print(f"Loaded Payments:     {len(payments)}")
    print(f"Loaded Transactions: {len(transactions)}")
    print("\nRoot Case Scenario:")
    print("  Company Account:  012180000000000001 (Empresa Operadora Nacional)")
    print("  Vendor Account:   012180000000000002 (Constructora Primaria)")
    print("  Shell Account:    012180000000000003 (Logística Fantasma)")
    print("  Cycle Flow:       1,000,000.00 MXN -> 920,000.00 MXN -> 740,000.00 MXN return")
    print("\nControl Group:")
    print("  Suppliers sharing Av. Reforma 222 (no inter-transfer, legitimate independent vendors)")
    print("Successfully initialized demo scenario.")


if __name__ == "__main__":
    main()
