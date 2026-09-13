"""Repository layer (`backend/repositories/`, TASK-001).

Two things are being pinned here.

**The boundary.** `interfaces.py` must not import a database driver —
that is what lets the agent tools, the detection pipeline and the API be
built before the database exists, and what stops any of them reaching
around the repository into SQL.

**The query semantics.** Ordering, inclusivity and what "no results"
means are decided once, here, rather than re-decided per module. A
detector that assumes transactions arrive in date order and a repository
that does not guarantee it produce a money trail that is wrong rather
than absent.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from truelock.database.repositories import (
    AccountRepository,
    EntityRepository,
    InMemoryRepositories,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)
from truelock.domain.models import (
    Account,
    EfosStatus,
    Entity,
    Invoice,
    Payment,
    Provider,
    Transaction,
)

UUID_A = "123e4567-e89b-12d3-a456-426614174000"
UUID_B = "223e4567-e89b-12d3-a456-426614174001"


@pytest.fixture
def repos() -> InMemoryRepositories:
    return InMemoryRepositories().load([
        Provider(rfc="ABC010101AAA", name="Acme", efos_status=EfosStatus.DEFINITIVE),
        Provider(rfc="DEF020202BBB", name="Beta", efos_status=EfosStatus.UNKNOWN),
        Entity(id="E-1", name="Acme", entity_type="company", rfc="ABC010101AAA"),
        Account(account_no="ACC-1", entity_id="E-1", bank="BBVA"),
        Account(account_no="ACC-2", entity_id="E-1"),
        Invoice(uuid=UUID_A, provider_rfc="ABC010101AAA", receiver_rfc="XYZ020202BBB",
                issue_date=date(2026, 1, 15), amount=1000.0),
        Invoice(uuid=UUID_B, provider_rfc="ABC010101AAA", receiver_rfc="XYZ020202BBB",
                issue_date=date(2026, 3, 1), amount=2000.0),
        Payment(id="P-1", related_invoice_uuid=UUID_A,
                payment_date=date(2026, 1, 20), amount=1000.0),
        Transaction(id="T-1", from_account="ACC-1", to_account="ACC-2",
                    transaction_date=date(2026, 1, 20), amount=1000.0,
                    related_payment_id="P-1"),
        Transaction(id="T-2", from_account="ACC-2", to_account="ACC-3",
                    transaction_date=date(2026, 1, 21), amount=900.0),
    ])


class TestTheBoundaryHolds:
    def test_interfaces_import_no_database_driver(self):
        """TASK-001 acceptance criterion 4, checked rather than asserted in prose."""
        source = (
            Path(__file__).resolve().parents[2]
            / "backend" / "src" / "truelock" / "database" / "repositories" / "interfaces.py"
        ).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        drivers = {"psycopg", "psycopg2", "sqlalchemy", "asyncpg", "sqlite3", "database"}
        assert not (imported & drivers), (
            f"backend/repositories/interfaces.py imports {sorted(imported & drivers)}; "
            "the read surface must not depend on the database, or nothing downstream "
            "can be built before it exists"
        )

    @pytest.mark.parametrize(
        "attribute,protocol",
        [
            ("providers", ProviderRepository), ("entities", EntityRepository),
            ("invoices", InvoiceRepository), ("payments", PaymentRepository),
            ("transactions", TransactionRepository), ("accounts", AccountRepository),
        ],
    )
    def test_the_in_memory_implementation_satisfies_its_protocol(
        self, repos, attribute, protocol
    ):
        assert isinstance(getattr(repos, attribute), protocol)


class TestLookups:
    def test_a_known_key_returns_the_record(self, repos):
        assert repos.invoices.get(UUID_A).amount == 1000.0

    def test_an_unknown_key_returns_none_rather_than_raising(self, repos):
        """Absence is a normal answer; the agent loop must not take an exception for it."""
        assert repos.invoices.get("nope") is None
        assert repos.providers.get("NOSUCHRFC") is None
        assert repos.accounts.get("ACC-999") is None

    def test_provider_lookup_is_case_insensitive(self, repos):
        """RFCs are normalised on entities; lookups must agree or joins miss."""
        assert repos.providers.get("abc010101aaa") is not None

    def test_entity_lookup_by_rfc(self, repos):
        assert repos.entities.get_by_rfc("abc010101aaa").id == "E-1"


class TestQuerySemantics:
    def test_invoices_by_provider_are_date_ordered(self, repos):
        invoices = repos.invoices.list_by_provider("ABC010101AAA")
        assert [item.uuid for item in invoices] == [UUID_A, UUID_B]

    def test_a_period_query_includes_both_endpoints(self, repos):
        found = repos.invoices.list_in_period(date(2026, 1, 15), date(2026, 3, 1))
        assert len(found) == 2

    def test_a_period_query_excludes_outside(self, repos):
        found = repos.invoices.list_in_period(date(2026, 1, 16), date(2026, 2, 28))
        assert found == []

    def test_a_reversed_period_is_an_error_not_an_empty_result(self, repos):
        """Silently returning nothing would read as 'no invoices', not 'bad query'."""
        with pytest.raises(ValueError):
            repos.invoices.list_in_period(date(2026, 3, 1), date(2026, 1, 1))

    def test_outgoing_and_incoming_are_distinct_directions(self, repos):
        assert [item.id for item in repos.transactions.list_outgoing("ACC-2")] == ["T-2"]
        assert [item.id for item in repos.transactions.list_incoming("ACC-2")] == ["T-1"]

    def test_transactions_are_date_ordered(self, repos):
        """The money-flow graph depends on this ordering."""
        assert [item.id for item in repos.transactions.list()] == ["T-1", "T-2"]

    def test_payments_for_an_invoice(self, repos):
        assert [item.id for item in repos.payments.list_for_invoice(UUID_A)] == ["P-1"]

    def test_an_invoice_with_no_payment_returns_empty(self, repos):
        """An unpaid invoice is a finding, so it must be expressible, not an error."""
        assert repos.payments.list_for_invoice(UUID_B) == []

    def test_transactions_for_a_payment(self, repos):
        assert [item.id for item in repos.transactions.list_for_payment("P-1")] == ["T-1"]

    def test_accounts_for_an_entity(self, repos):
        assert [item.account_no for item in repos.accounts.list_for_entity("E-1")] == [
            "ACC-1", "ACC-2",
        ]

    def test_providers_by_efos_status(self, repos):
        listed = repos.providers.list_by_efos_status("DEFINITIVE")
        assert [item.rfc for item in listed] == ["ABC010101AAA"]

    def test_efos_status_accepts_the_enum_too(self, repos):
        assert len(repos.providers.list_by_efos_status(EfosStatus.DEFINITIVE)) == 1


class TestPagination:
    def test_limit_and_offset_page_a_stable_order(self, repos):
        first = repos.invoices.list(limit=1, offset=0)
        second = repos.invoices.list(limit=1, offset=1)
        assert first[0].uuid == UUID_A
        assert second[0].uuid == UUID_B

    def test_paging_past_the_end_is_empty(self, repos):
        assert repos.invoices.list(limit=10, offset=99) == []

    def test_negative_paging_is_refused(self, repos):
        """Python would silently wrap a negative offset to the end of the list."""
        with pytest.raises(ValueError):
            repos.invoices.list(limit=10, offset=-1)


class TestLoading:
    def test_load_dispatches_by_type(self, repos):
        assert len(repos) == 10

    def test_loading_a_non_entity_is_refused(self):
        with pytest.raises(TypeError):
            InMemoryRepositories().load([{"not": "an entity"}])

    def test_loading_the_same_key_twice_replaces_rather_than_duplicates(self):
        repos = InMemoryRepositories().load([
            Account(account_no="ACC-1", entity_id="E-1", bank="BBVA"),
            Account(account_no="ACC-1", entity_id="E-1", bank="Santander"),
        ])
        assert len(repos) == 1
        assert repos.accounts.get("ACC-1").bank == "Santander"
