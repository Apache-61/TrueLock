"""Deterministic fraud detectors — registry façade over pure rule functions."""
from __future__ import annotations

from truelock.database.repositories.interfaces import (
    AccountRepository,
    EntityRepository,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)
from truelock.detection.dataset import CanonicalDataset
from truelock.detection.rules import (
    circular_flow,
    duplicate_payment,
    rapid_pass_through,
    run_all_detectors,
    shared_address_control,
)
from truelock.detection.scoring import aggregate_signals
from truelock.detection.signals import DetectorSignal
from truelock.domain.models.investigation import Lead


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

    def dataset(self) -> CanonicalDataset:
        return CanonicalDataset(
            entities=self.entities,
            providers=self.providers,
            accounts=self.accounts,
            transactions=self.transactions,
            invoices=self.invoices,
            payments=self.payments,
        )

    def collect_signals(self) -> list[DetectorSignal]:
        """Run every registered detector. Same dataset → same signals."""
        return run_all_detectors(self.dataset())

    def run_all(self) -> list[Lead]:
        """Execute all deterministic detectors and return prioritized leads."""
        return aggregate_signals(self.collect_signals())

    def detect_round_trip_cycles(self) -> list[Lead]:
        return aggregate_signals(circular_flow.detect(self.dataset()))

    def detect_rapid_pass_through(self) -> list[Lead]:
        return aggregate_signals(rapid_pass_through.detect(self.dataset()))

    def detect_duplicate_payments(self) -> list[Lead]:
        return aggregate_signals(duplicate_payment.detect(self.dataset()))

    def generate_control_leads(self) -> list[Lead]:
        return aggregate_signals(shared_address_control.detect(self.dataset()))
