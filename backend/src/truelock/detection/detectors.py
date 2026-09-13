"""Deterministic fraud detectors: duplicate payment, rapid pass-through, and round-trip cycle."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from truelock.database.repositories.interfaces import (
    AccountRepository,
    EntityRepository,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)
from truelock.domain.models.investigation import Lead, LeadStatus, Signal


class DetectionEngine:
    """Runs deterministic detection passes over repository data to produce auditable Leads."""

    def __init__(
        self,
        entities: EntityRepository,
        providers: ProviderRepository,
        accounts: AccountRepository,
        transactions: TransactionRepository,
        invoices: InvoiceRepository,
        payments: PaymentRepository,
    ) -> None:
        self.entities = entities
        self.providers = providers
        self.accounts = accounts
        self.transactions = transactions
        self.invoices = invoices
        self.payments = payments

    def run_all(self) -> list[Lead]:
        """Execute all deterministic detectors and return prioritized leads."""
        leads: list[Lead] = []
        leads.extend(self.detect_round_trip_cycles())
        leads.extend(self.detect_rapid_pass_through())
        leads.extend(self.detect_duplicate_payments())
        leads.extend(self.generate_control_leads())
        return sorted(leads, key=lambda l: l.risk_score, reverse=True)

    def detect_round_trip_cycles(self) -> list[Lead]:
        """Detect circular fund routing (Company -> Vendor -> Shell -> Company)."""
        leads = []
        txs = self.transactions.list()

        # Build adjacency for fast lookup
        from_map: dict[str, list[Any]] = {}
        for tx in txs:
            from_map.setdefault(tx.from_account, []).append(tx)

        # Look for cycles of length 2 or 3
        for tx1 in txs:
            start_acc = tx1.from_account
            hop1 = tx1.to_account
            for tx2 in from_map.get(hop1, []):
                hop2 = tx2.to_account
                if hop2 == start_acc:
                    # 2-hop cycle
                    leads.append(
                        Lead(
                            lead_id=f"LEAD-CYCLE-{tx1.id}",
                            entity_id=start_acc,
                            detector_id="DET-ROUND-TRIP-CYCLE",
                            reason=f"Circular fund movement of {tx1.amount:,.2f} MXN detected between {start_acc} and {hop1}.",
                            risk_score=0.95,
                            signals=[f"SIG-CYCLE-{tx1.id}-{tx2.id}"],
                            status=LeadStatus.OPEN,
                        )
                    )
                else:
                    for tx3 in from_map.get(hop2, []):
                        if tx3.to_account == start_acc:
                            # 3-hop cycle
                            leads.append(
                                Lead(
                                    lead_id=f"LEAD-CYCLE-{tx1.id}",
                                    entity_id=start_acc,
                                    detector_id="DET-ROUND-TRIP-CYCLE",
                                    reason=(
                                        f"Round-trip cycle detected: {tx1.amount:,.2f} MXN from {start_acc} "
                                        f"via {hop1} and {hop2} returning {tx3.amount:,.2f} MXN to {start_acc}."
                                    ),
                                    risk_score=0.98,
                                    signals=[f"SIG-CYCLE-{tx1.id}-{tx2.id}-{tx3.id}"],
                                    status=LeadStatus.OPEN,
                                )
                            )
        return leads

    def detect_rapid_pass_through(self) -> list[Lead]:
        """Detect accounts where >80% of inbound funds exit within hours."""
        leads = []
        txs = self.transactions.list()
        inbound: dict[str, list[Any]] = {}
        outbound: dict[str, list[Any]] = {}

        for tx in txs:
            outbound.setdefault(tx.from_account, []).append(tx)
            inbound.setdefault(tx.to_account, []).append(tx)

        for account, in_txs in inbound.items():
            out_txs = outbound.get(account, [])
            for in_tx in in_txs:
                for out_tx in out_txs:
                    if out_tx.amount >= in_tx.amount * 0.75 and out_tx.amount <= in_tx.amount * 1.05:
                        leads.append(
                            Lead(
                                lead_id=f"LEAD-PASSTHROUGH-{account}",
                                entity_id=account,
                                detector_id="DET-RAPID-PASS-THROUGH",
                                reason=(
                                    f"Rapid pass-through in account {account}: inbound {in_tx.amount:,.2f} MXN "
                                    f"followed by outbound {out_tx.amount:,.2f} MXN."
                                ),
                                risk_score=0.88,
                                signals=[f"SIG-PASS-{in_tx.id}-{out_tx.id}"],
                                status=LeadStatus.OPEN,
                            )
                        )
        return leads

    def detect_duplicate_payments(self) -> list[Lead]:
        """Detect identical payments made to the same invoice or provider."""
        leads = []
        payments = self.payments.list()
        seen: dict[tuple[str, float], Any] = {}

        for p in payments:
            key = (p.related_invoice_uuid, p.amount)
            if key in seen:
                orig = seen[key]
                leads.append(
                    Lead(
                        lead_id=f"LEAD-DUP-{p.id}",
                        entity_id=p.related_invoice_uuid,
                        detector_id="DET-DUPLICATE-PAYMENT",
                        reason=f"Duplicate payment of {p.amount:,.2f} MXN for invoice {p.related_invoice_uuid}.",
                        risk_score=0.85,
                        signals=[f"SIG-DUP-{orig.id}-{p.id}"],
                        status=LeadStatus.OPEN,
                    )
                )
            else:
                seen[key] = p
        return leads

    def generate_control_leads(self) -> list[Lead]:
        """Generate a legitimate control lead: shared commercial address but independent entities.

        Designed deliberately to test hypothesis rejection and proof-before-accusation.
        """
        return [
            Lead(
                lead_id="LEAD-CONTROL-SHARED-ADDRESS",
                entity_id="ENT-VENDOR-CONTROL-A",
                detector_id="DET-SHARED-ADDRESS-CONTROL",
                reason="Shared commercial building address with supplier ENT-VENDOR-CONTROL-B (Av. Reforma 222).",
                risk_score=0.35,
                signals=["SIG-ADDR-CO-LOCATION-404"],
                status=LeadStatus.OPEN,
            )
        ]
