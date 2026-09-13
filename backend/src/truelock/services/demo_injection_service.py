"""Judge-controlled injection of hidden fraud patterns into the demo dataset."""
from __future__ import annotations

import hashlib
from typing import Any

from truelock.agent.investigator import ForensicInvestigator
from truelock.agent.tools import ToolRegistry
from truelock.database.repositories.memory import InMemoryRepositories
from truelock.database.repositories.postgres import PostgresRepositories, deterministic_uuid
from truelock.detection.detectors import DetectionEngine
from truelock.seeder.injection_scenarios import SCENARIOS, InjectionScenario
from truelock.services.investigation_service import InvestigationService


def _sha256_hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class DemoInjectionService:
    """Expose hidden scenarios without pre-loading them in the default demo."""

    def list_scenarios(self) -> list[dict[str, str]]:
        return [
            {"scenario_id": key, "description": fn.__doc__ or key}
            for key, fn in SCENARIOS.items()
        ]

    def inject(
        self,
        service: InvestigationService,
        *,
        scenario_id: str | None = None,
    ) -> dict[str, Any]:
        chosen = scenario_id or "hidden_pass_through"
        if chosen not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario_id {chosen!r}. Available: {', '.join(sorted(SCENARIOS))}"
            )

        if service.database:
            meta = self._inject_postgres(service.database, chosen)
        else:
            meta = self._inject_memory(service, chosen)

        leads = service.refresh_leads()
        injected_leads = sorted(leads, key=lambda item: item.risk_score, reverse=True)
        primary = next(
            (
                lead
                for lead in injected_leads
                if lead.lead_id.startswith("LEAD-") and lead.risk_score >= 0.7
            ),
            injected_leads[0] if injected_leads else None,
        )
        return {
            "scenario_id": meta.scenario_id,
            "description": meta.description,
            "entity_id": meta.primary_entity_id,
            "lead_id": primary.lead_id if primary else None,
            "lead_count": len(leads),
            "message": f"Injected scenario {meta.scenario_id}. Run detectors to surface new leads.",
        }

    def clear_analysis(
        self,
        service: InvestigationService,
        *,
        remove_injections: bool = True,
    ) -> dict[str, Any]:
        """Wipe threads/data to an empty workspace; do not surface leads until Load demo."""
        del remove_injections
        if service.database:
            deleted = service.database.wipe_workspace()
            service._cases.clear()
            service._steps.clear()
            service._evidence.clear()
            service._leads.clear()
            return {
                "status": "cleared",
                "mode": "postgres",
                "remove_injections": True,
                "full_reset": True,
                "deleted": deleted,
                "lead_count": 0,
                "message": (
                    "Workspace cleared: no threads, evidence, imports or leads. "
                    "Use Load demo or upload a dataset to continue."
                ),
            }

        service.repo = InMemoryRepositories()
        data = service.repo
        service.detector = DetectionEngine(
            entities=data.entities,
            providers=data.providers,
            accounts=data.accounts,
            transactions=data.transactions,
            invoices=data.invoices,
            payments=data.payments,
        )
        service.tools = ToolRegistry(
            entities=data.entities,
            providers=data.providers,
            accounts=data.accounts,
            transactions=data.transactions,
            invoices=data.invoices,
            payments=data.payments,
        )
        service.investigator = ForensicInvestigator(service.tools, service.gemini)
        service._cases.clear()
        service._steps.clear()
        service._evidence.clear()
        service._leads.clear()
        return {
            "status": "cleared",
            "mode": "memory",
            "remove_injections": True,
            "full_reset": True,
            "deleted": {"analysis": {}, "financial": {}},
            "lead_count": 0,
            "message": "In-memory workspace cleared. Load demo or wait for imports.",
        }

    def load_demo(self, service: InvestigationService) -> dict[str, Any]:
        """Seed CASE-DEMO-001 and run detectors so leads appear."""
        if service.database:
            deleted = service.database.reset_canonical_demo()
            service._cases.clear()
            service._steps.clear()
            service._evidence.clear()
            service._leads.clear()
            leads = service.refresh_leads()
            return {
                "status": "loaded",
                "mode": "postgres",
                "deleted": deleted,
                "lead_count": len(leads),
                "message": f"Demo CASE-DEMO-001 loaded. {len(leads)} leads ready.",
            }

        from truelock.seeder.demo_scenario import load_demo_scenario

        service.repo = load_demo_scenario()
        data = service.repo
        service.detector = DetectionEngine(
            entities=data.entities,
            providers=data.providers,
            accounts=data.accounts,
            transactions=data.transactions,
            invoices=data.invoices,
            payments=data.payments,
        )
        service.tools = ToolRegistry(
            entities=data.entities,
            providers=data.providers,
            accounts=data.accounts,
            transactions=data.transactions,
            invoices=data.invoices,
            payments=data.payments,
        )
        service.investigator = ForensicInvestigator(service.tools, service.gemini)
        service._cases.clear()
        service._steps.clear()
        service._evidence.clear()
        service._leads.clear()
        leads = service.refresh_leads()
        return {
            "status": "loaded",
            "mode": "memory",
            "lead_count": len(leads),
            "message": f"In-memory demo loaded. {len(leads)} leads ready.",
        }

    def _inject_memory(
        self, service: InvestigationService, scenario_id: str
    ) -> InjectionScenario:
        repo = service.repo
        if not isinstance(repo, InMemoryRepositories):
            raise RuntimeError("In-memory repository required for injection")
        return SCENARIOS[scenario_id](repo)

    def _inject_postgres(
        self, database: PostgresRepositories, scenario_id: str
    ) -> InjectionScenario:
        case_id = database.canonical_case_id()
        if not case_id:
            raise ValueError("No canonical case found; run seed_demo.sh first")
        if scenario_id == "hidden_pass_through":
            return self._pg_hidden_pass_through(database, case_id)
        if scenario_id == "hidden_duplicate_payment":
            return self._pg_hidden_duplicate_payment(database, case_id)
        raise ValueError(f"Unsupported PostgreSQL scenario_id {scenario_id!r}")

    def _pg_hidden_pass_through(
        self, database: PostgresRepositories, case_id: Any
    ) -> InjectionScenario:
        source_file_id = deterministic_uuid("source:inject:hidden_pass_through")
        entity_vendor = deterministic_uuid("entity:ENT-HIDDEN-VENDOR-001")
        entity_shell = deterministic_uuid("entity:ENT-HIDDEN-SHELL-001")
        account_vendor = deterministic_uuid("account:012180000000000091")
        account_shell = deterministic_uuid("account:012180000000000092")
        tx_root = deterministic_uuid("tx:TX-HIDDEN-ROOT-001")
        tx_hop = deterministic_uuid("tx:TX-HIDDEN-HOP-001")

        with database.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO truelock.source_files (
                    source_file_id, case_id, original_filename, dataset_kind,
                    byte_size, sha256, parser_name, parser_version, status, record_count
                ) VALUES (%s, %s, 'injected_hidden.csv', 'BANK', 1, %s,
                          'inject-fraud', '1.0.0', 'IMPORTED', 2)
                ON CONFLICT DO NOTHING
                """,
                (source_file_id, case_id, _sha256_hex("inject:hidden_pass_through")),
            )
            for entity_id, rfc, name, ext_id in (
                (entity_vendor, "SOV240101AA1", "Servicios Opacos del Centro SA de CV", "ENT-HIDDEN-VENDOR-001"),
                (entity_shell, "ESC240215BB2", "Enlace Rapido de Capital SC", "ENT-HIDDEN-SHELL-001"),
            ):
                cur.execute(
                    """
                    INSERT INTO truelock.entities (
                        entity_id, case_id, entity_type, canonical_name, legal_name, rfc,
                        source_file_id, source_locator, raw_payload
                    ) VALUES (%s, %s, 'SUPPLIER', %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        entity_id,
                        case_id,
                        name,
                        name,
                        rfc,
                        source_file_id,
                        ext_id,
                        f'{{"external_entity_id":"{ext_id}"}}',
                    ),
                )
            company_entity = database.fetch_one(
                "SELECT entity_id FROM truelock.entities WHERE case_id = %s AND rfc = 'EDE180101AA1' LIMIT 1",
                (case_id,),
            )
            company_account = database.fetch_one(
                """
                SELECT ba.bank_account_id FROM truelock.bank_accounts ba
                WHERE ba.case_id = %s AND ba.account_number = '012180000000000001' LIMIT 1
                """,
                (case_id,),
            )
            if not company_entity or not company_account:
                raise ValueError("Canonical demo entities missing; re-run seed_demo.sh")

            for acct_id, acct_no, entity_id in (
                (account_vendor, "012180000000000091", entity_vendor),
                (account_shell, "012180000000000092", entity_shell),
            ):
                cur.execute(
                    """
                    INSERT INTO truelock.bank_accounts (
                        bank_account_id, case_id, account_fingerprint, account_number,
                        masked_account, bank_name, currency, source_file_id
                    ) VALUES (%s, %s, %s, %s, %s, 'Injected', 'MXN', %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (acct_id, case_id, _sha256_hex(f"account-fingerprint:{acct_no}"), acct_no, "*" * 12 + acct_no[-4:], source_file_id),
                )
                cur.execute(
                    """
                    INSERT INTO truelock.entity_bank_accounts (entity_id, bank_account_id, source_file_id, source_locator)
                    VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                    """,
                    (entity_id, acct_id, source_file_id, acct_no),
                )

            cur.execute(
                """
                INSERT INTO truelock.bank_transactions (
                    bank_transaction_id, case_id, source_file_id, source_locator,
                    external_transaction_id, observed_bank_account_id, booked_at, value_date,
                    direction, origin_bank_account_id, destination_bank_account_id,
                    origin_entity_id, destination_entity_id, amount, currency, amount_mxn
                ) VALUES
                (%s, %s, %s, 'inject:1', 'TX-HIDDEN-ROOT-001', %s,
                 '2026-09-02T10:00:00Z', '2026-09-02', 'DEBIT', %s, %s, %s, %s, 550000, 'MXN', 550000),
                (%s, %s, %s, 'inject:2', 'TX-HIDDEN-HOP-001', %s,
                 '2026-09-02T11:00:00Z', '2026-09-02', 'DEBIT', %s, %s, %s, %s, 500500, 'MXN', 500500)
                ON CONFLICT DO NOTHING
                """,
                (
                    tx_root,
                    case_id,
                    source_file_id,
                    company_account["bank_account_id"],
                    company_account["bank_account_id"],
                    account_vendor,
                    company_entity["entity_id"],
                    entity_vendor,
                    tx_hop,
                    case_id,
                    source_file_id,
                    account_vendor,
                    account_vendor,
                    account_shell,
                    entity_vendor,
                    entity_shell,
                ),
            )

        return InjectionScenario(
            scenario_id="hidden_pass_through",
            description="550k MXN to a new opaque vendor with 91% rapid outbound transfer.",
            primary_entity_id="ENT-HIDDEN-VENDOR-001",
        )

    def _pg_hidden_duplicate_payment(
        self, database: PostgresRepositories, case_id: Any
    ) -> InjectionScenario:
        """Second full payment against the canonical root invoice UUID."""
        source_file_id = deterministic_uuid("source:inject:hidden_duplicate_payment")
        payment_id = deterministic_uuid("payment:PMT-HIDDEN-DUP-001")
        payment_doc_id = deterministic_uuid("payment_doc:PMT-HIDDEN-DUP-001")
        tx_id = deterministic_uuid("tx:TX-HIDDEN-DUP-001")
        invoice = database.fetch_one(
            """
            SELECT invoice_id FROM truelock.invoices
            WHERE case_id = %s AND uuid = '11111111-2222-3333-4444-555555555555'
            LIMIT 1
            """,
            (case_id,),
        )
        company_entity = database.fetch_one(
            "SELECT entity_id FROM truelock.entities WHERE case_id = %s AND rfc = 'EDE180101AA1' LIMIT 1",
            (case_id,),
        )
        vendor_entity = database.fetch_one(
            "SELECT entity_id FROM truelock.entities WHERE case_id = %s AND rfc = 'CPR190515BB2' LIMIT 1",
            (case_id,),
        )
        company_account = database.fetch_one(
            """
            SELECT bank_account_id FROM truelock.bank_accounts
            WHERE case_id = %s AND account_number = '012180000000000001' LIMIT 1
            """,
            (case_id,),
        )
        vendor_account = database.fetch_one(
            """
            SELECT bank_account_id FROM truelock.bank_accounts
            WHERE case_id = %s AND account_number = '012180000000000002' LIMIT 1
            """,
            (case_id,),
        )
        if not all([invoice, company_entity, vendor_entity, company_account, vendor_account]):
            raise ValueError("Canonical demo entities missing; re-run seed_demo.sh")

        with database.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO truelock.source_files (
                    source_file_id, case_id, original_filename, dataset_kind,
                    byte_size, sha256, parser_name, parser_version, status, record_count
                ) VALUES (%s, %s, 'injected_duplicate.csv', 'BANK', 1, %s,
                          'inject-fraud', '1.0.0', 'IMPORTED', 1)
                ON CONFLICT DO NOTHING
                """,
                (source_file_id, case_id, _sha256_hex("inject:hidden_duplicate_payment")),
            )
            cur.execute(
                """
                INSERT INTO truelock.payment_complements (
                    payment_id, case_id, source_file_id, source_locator, payment_cfdi_uuid,
                    payment_date, currency, payment_form, payment_amount, amount_mxn,
                    operation_number, external_payment_id, record_sha256, raw_payload
                ) VALUES (
                    %s, %s, %s, 'inject:dup:1', '11111111-2222-3333-4444-555555555555',
                    '2026-09-03T14:00:00Z', 'MXN', '03', 1000000, 1000000,
                    'PMT-HIDDEN-DUP-001', 'PMT-HIDDEN-DUP-001', %s,
                    '{"external_payment_id":"PMT-HIDDEN-DUP-001"}'::jsonb
                )
                ON CONFLICT DO NOTHING
                """,
                (payment_id, case_id, source_file_id, _sha256_hex("inject:dup:payment")),
            )
            cur.execute(
                """
                INSERT INTO truelock.payment_documents (
                    payment_document_id, payment_id, invoice_id, related_document_uuid,
                    document_currency, installment_no, previous_balance, amount_paid, remaining_balance
                ) VALUES (%s, %s, %s, '11111111-2222-3333-4444-555555555555',
                          'MXN', 2, 1000000, 1000000, 0)
                ON CONFLICT DO NOTHING
                """,
                (payment_doc_id, payment_id, invoice["invoice_id"]),
            )
            cur.execute(
                """
                INSERT INTO truelock.bank_transactions (
                    bank_transaction_id, case_id, source_file_id, source_locator,
                    external_transaction_id, related_payment_external_id, observed_bank_account_id,
                    booked_at, value_date, direction, origin_bank_account_id, destination_bank_account_id,
                    origin_entity_id, destination_entity_id, amount, currency, amount_mxn
                ) VALUES (
                    %s, %s, %s, 'inject:dup:tx', 'TX-HIDDEN-DUP-001', 'PMT-HIDDEN-DUP-001', %s,
                    '2026-09-03T14:00:00Z', '2026-09-03', 'DEBIT', %s, %s, %s, %s,
                    1000000, 'MXN', 1000000
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    tx_id,
                    case_id,
                    source_file_id,
                    company_account["bank_account_id"],
                    company_account["bank_account_id"],
                    vendor_account["bank_account_id"],
                    company_entity["entity_id"],
                    vendor_entity["entity_id"],
                ),
            )

        return InjectionScenario(
            scenario_id="hidden_duplicate_payment",
            description="Second full payment for the canonical root invoice UUID.",
            primary_entity_id="ENT-VENDOR-001",
        )
