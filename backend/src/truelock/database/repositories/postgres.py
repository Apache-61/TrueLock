"""PostgreSQL repository implementations for the production TrueLock path.

The public repository protocols remain intentionally small.  This module owns
the SQL boundary, uses a shared connection pool, and maps the canonical
``truelock`` schema back to the Pydantic records consumed by the detector and
agent layers.  All statements are parameterized.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any, Iterator
from urllib.parse import urlparse

from truelock.domain.models import Account, EfosStatus, Entity, Invoice, Payment, Provider, Transaction


def validate_database_url(value: str) -> str:
    """Reject malformed or non-PostgreSQL URLs before opening a pool."""
    parsed = urlparse(value)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
    return value


class PostgresRepositories:
    """Pooled, synchronous repositories backed by the canonical SQL schema."""

    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 5) -> None:
        validate_database_url(database_url)
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - depends on installation
            raise RuntimeError(
                "PostgreSQL persistence requires the 'psycopg[pool]' package. "
                "Install project dependencies before configuring DATABASE_URL."
            ) from exc
        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": False, "row_factory": dict_row},
            open=True,
        )
        self.providers = _ProviderRepository(self)
        self.entities = _EntityRepository(self)
        self.accounts = _AccountRepository(self)
        self.invoices = _InvoiceRepository(self)
        self.payments = _PaymentRepository(self)
        self.transactions = _TransactionRepository(self)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Return one pooled connection and guarantee rollback on failures."""
        with self._pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query, params)

    def check_health(self) -> bool:
        return self.fetch_one("SELECT 1 AS ok") == {"ok": 1}

    def list_lead_records(self) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT l.lead_id, l.display_id, l.title, l.risk_score, l.status,
                   l.reason_summary,
                   (array_agg(le.entity_id::text ORDER BY le.entity_id::text)
                     FILTER (WHERE le.entity_id IS NOT NULL))[1] AS entity_id,
                   coalesce(array_agg(DISTINCT a.detector_code)
                     FILTER (WHERE a.detector_code IS NOT NULL), ARRAY[]::text[]) AS detector_codes
            FROM truelock.leads l
            LEFT JOIN truelock.lead_entities le ON le.lead_id = l.lead_id
            LEFT JOIN truelock.lead_anomalies la ON la.lead_id = l.lead_id
            LEFT JOIN truelock.anomalies a ON a.anomaly_id = la.anomaly_id
            GROUP BY l.lead_id, l.display_id, l.title, l.risk_score, l.status,
                     l.reason_summary, l.created_at
            ORDER BY l.risk_score DESC, l.created_at
            """
        )
        return [_lead_dict(row) for row in rows]

    def list_case_records(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT c.display_id AS case_id, c.title, c.status, c.opened_at,
                   count(DISTINCT l.lead_id) AS lead_count,
                   count(DISTINCT f.finding_id) FILTER (WHERE f.status = 'SUPPORTED') AS supported_finding_count
            FROM truelock.cases c
            LEFT JOIN truelock.leads l ON l.case_id = c.case_id
            LEFT JOIN truelock.findings f ON f.case_id = c.case_id
            GROUP BY c.case_id, c.display_id, c.title, c.status, c.opened_at
            ORDER BY c.opened_at DESC
            """
        )

    def get_lead_record(self, lead_id: str) -> dict[str, Any] | None:
        return next((row for row in self.list_lead_records() if str(row["lead_id"]) == lead_id), None)

    def investigation_details(self, case_reference: str) -> dict[str, Any] | None:
        """Build the API investigation payload entirely from persisted records."""
        case_row = self.fetch_one(
            """
            SELECT c.case_id, c.display_id, c.title
            FROM truelock.cases c
            WHERE c.case_id::text = %s OR c.display_id = %s
            """,
            (case_reference, case_reference),
        )
        if not case_row:
            return None
        finding = self.fetch_one(
            """
            SELECT * FROM truelock.v_case_findings
            WHERE case_id = %s AND status = 'SUPPORTED'
            ORDER BY finding_id LIMIT 1
            """,
            (case_row["case_id"],),
        )
        thread = self.fetch_one(
            """
            SELECT t.thread_id, t.hypothesis_claim, t.status
            FROM truelock.investigation_threads t
            WHERE t.case_id = %s
            ORDER BY t.created_at LIMIT 1
            """,
            (case_row["case_id"],),
        )
        evidence = self.fetch_all(
            """
            SELECT e.evidence_id, e.evidence_type, e.record_id, e.source_file_id,
                   e.source_locator, e.facts, e.created_at,
                   coalesce(te.role::text, 'CONTEXTUAL') AS role
            FROM truelock.evidence e
            LEFT JOIN truelock.thread_evidence te ON te.evidence_id = e.evidence_id
            WHERE e.case_id = %s
            ORDER BY e.created_at, e.evidence_id
            """,
            (case_row["case_id"],),
        )
        steps = self.fetch_all(
            """
            SELECT step_id, thread_id, sequence, action, tool_name, reason_summary,
                   tool_inputs, result_summary, provenance, errors, decision,
                   started_at, completed_at, duration_ms,
                   input_evidence_ids, result_evidence_ids
            FROM truelock.v_investigation_timeline
            WHERE case_id = %s
            ORDER BY started_at, sequence
            """,
            (case_row["case_id"],),
        )
        return {
            "case": {
                "case_id": case_row["display_id"],
                "status": "SUBSTANTIATED" if finding else "UNSUBSTANTIATED",
                "hypothesis": thread["hypothesis_claim"] if thread else case_row["title"],
                "providers_involved": [],
                "amount_involved": _number(finding["supported_exposure_mxn"]) if finding else 0,
                "supporting_evidence": [str(row["evidence_id"]) for row in evidence],
                "confidence_level": finding["confidence_label"] if finding else "MEDIUM",
                "limitations": finding["limitations"] if finding else [],
                "citations": [],
            },
            "steps": [_step_dict(row) for row in steps],
            "evidence": [_evidence_dict(row) for row in evidence],
            "finding": _row_json(finding) if finding else None,
            "thread_id": str(thread["thread_id"]) if thread else None,
        }

    def existing_investigation_for_lead(self, lead_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT c.display_id
            FROM truelock.investigations i
            JOIN truelock.cases c ON c.case_id = i.case_id
            WHERE i.lead_id::text = %s
            ORDER BY i.created_at DESC LIMIT 1
            """,
            (lead_id,),
        )
        return self.investigation_details(row["display_id"]) if row else None

    def money_trail(self, case_reference: str) -> dict[str, Any] | None:
        case = self.fetch_one(
            "SELECT case_id, display_id FROM truelock.cases WHERE case_id::text = %s OR display_id = %s",
            (case_reference, case_reference),
        )
        if not case:
            return None
        edges = self.fetch_all(
            """
            SELECT * FROM truelock.v_money_trail
            WHERE case_id = %s ORDER BY root_flow_id, path_sequence, booked_at
            """,
            (case["case_id"],),
        )
        entities = self.fetch_all(
            """
            SELECT DISTINCT e.entity_id, e.canonical_name, e.entity_type, e.rfc
            FROM truelock.entities e
            JOIN (
              SELECT origin_entity_id AS entity_id FROM truelock.v_money_trail WHERE case_id = %s
              UNION
              SELECT destination_entity_id FROM truelock.v_money_trail WHERE case_id = %s
            ) used ON used.entity_id = e.entity_id
            ORDER BY e.canonical_name
            """,
            (case["case_id"], case["case_id"]),
        )
        return {"case_id": case["display_id"], "nodes": [_row_json(row) for row in entities], "edges": [_row_json(row) for row in edges]}

    def case_findings(self, case_reference: str) -> list[dict[str, Any]]:
        case = self.fetch_one(
            "SELECT case_id FROM truelock.cases WHERE case_id::text = %s OR display_id = %s",
            (case_reference, case_reference),
        )
        if not case:
            return []
        return [_row_json(row) for row in self.fetch_all(
            "SELECT * FROM truelock.v_case_findings WHERE case_id = %s ORDER BY finding_id",
            (case["case_id"],),
        )]

    def persist_question(
        self, case_reference: str, question: str, answer: str, evidence_ids: list[str], step_ids: list[str]
    ) -> None:
        case = self.fetch_one(
            "SELECT case_id FROM truelock.cases WHERE case_id::text = %s OR display_id = %s",
            (case_reference, case_reference),
        )
        if not case:
            raise ValueError("Case not found")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO truelock.case_questions (case_id, question, answer, certainty)
                VALUES (%s, %s, %s, %s) RETURNING question_id
                """,
                (case["case_id"], question, answer, "EVIDENCE_GROUNDED"),
            )
            question_id = cur.fetchone()[0]
            for evidence_id in evidence_ids:
                cur.execute(
                    "INSERT INTO truelock.case_question_evidence (question_id, evidence_id) VALUES (%s, %s)",
                    (question_id, evidence_id),
                )
            for step_id in step_ids:
                cur.execute(
                    "INSERT INTO truelock.case_question_steps (question_id, step_id) VALUES (%s, %s)",
                    (question_id, step_id),
                )


class _ProviderRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, rfc: str) -> Provider | None:
        row = self.db.fetch_one(
            """
            SELECT s.rfc, s.legal_name AS name, s.address_raw AS address,
                   v.status AS sat_status, v.snapshot_date
            FROM truelock.suppliers s
            LEFT JOIN truelock.v_latest_sat_69b v ON v.case_id = s.case_id AND v.rfc = s.rfc
            WHERE upper(s.rfc) = upper(%s) ORDER BY s.imported_at DESC LIMIT 1
            """,
            (rfc,),
        )
        return _provider(row) if row else None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Provider]:
        _page(limit, offset)
        rows = self.db.fetch_all(
            "SELECT rfc, legal_name AS name, address_raw AS address FROM truelock.suppliers ORDER BY rfc LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return [_provider(row) for row in rows]

    def list_by_efos_status(self, status: str) -> list[Provider]:
        wanted = str(getattr(status, "value", status))
        return [provider for provider in self.list() if provider.efos_status.value == wanted]


class _EntityRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, entity_id: str) -> Entity | None:
        row = self.db.fetch_one("SELECT entity_id, canonical_name, entity_type, rfc FROM truelock.entities WHERE entity_id::text = %s", (entity_id,))
        return _entity(row) if row else None

    def get_by_rfc(self, rfc: str) -> Entity | None:
        row = self.db.fetch_one(
            "SELECT entity_id, canonical_name, entity_type, rfc FROM truelock.entities WHERE upper(rfc) = upper(%s) ORDER BY created_at LIMIT 1",
            (rfc,),
        )
        return _entity(row) if row else None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Entity]:
        _page(limit, offset)
        return [_entity(row) for row in self.db.fetch_all(
            "SELECT entity_id, canonical_name, entity_type, rfc FROM truelock.entities ORDER BY entity_id LIMIT %s OFFSET %s",
            (limit, offset),
        )]


class _AccountRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, account_no: str) -> Account | None:
        row = self.db.fetch_one(
            """
            SELECT ba.account_number, ba.masked_account, ba.bank_name, eba.entity_id
            FROM truelock.bank_accounts ba
            JOIN truelock.entity_bank_accounts eba ON eba.bank_account_id = ba.bank_account_id
            WHERE ba.account_number = %s OR ba.masked_account = %s LIMIT 1
            """,
            (account_no, account_no),
        )
        return _account(row) if row else None

    def list_for_entity(self, entity_id: str) -> list[Account]:
        rows = self.db.fetch_all(
            """
            SELECT ba.account_number, ba.masked_account, ba.bank_name, eba.entity_id
            FROM truelock.entity_bank_accounts eba JOIN truelock.bank_accounts ba ON ba.bank_account_id = eba.bank_account_id
            WHERE eba.entity_id::text = %s ORDER BY ba.account_number
            """,
            (entity_id,),
        )
        return [_account(row) for row in rows]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Account]:
        _page(limit, offset)
        rows = self.db.fetch_all(
            """
            SELECT ba.account_number, ba.masked_account, ba.bank_name, eba.entity_id
            FROM truelock.entity_bank_accounts eba JOIN truelock.bank_accounts ba ON ba.bank_account_id = eba.bank_account_id
            ORDER BY ba.account_number LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return [_account(row) for row in rows]


class _InvoiceRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, uuid: str) -> Invoice | None:
        row = self.db.fetch_one("SELECT * FROM truelock.invoices WHERE uuid = %s ORDER BY imported_at LIMIT 1", (uuid,))
        return _invoice(row) if row else None

    def list_by_provider(self, provider_rfc: str) -> list[Invoice]:
        return [_invoice(row) for row in self.db.fetch_all(
            "SELECT * FROM truelock.invoices WHERE upper(rfc_issuer) = upper(%s) ORDER BY issue_timestamp, invoice_id",
            (provider_rfc,),
        )]

    def list_by_receiver(self, receiver_rfc: str) -> list[Invoice]:
        return [_invoice(row) for row in self.db.fetch_all(
            "SELECT * FROM truelock.invoices WHERE upper(rfc_receiver) = upper(%s) ORDER BY issue_timestamp, invoice_id",
            (receiver_rfc,),
        )]

    def list_in_period(self, start: date, end: date) -> list[Invoice]:
        if start > end:
            raise ValueError(f"start {start} is after end {end}")
        return [_invoice(row) for row in self.db.fetch_all(
            "SELECT * FROM truelock.invoices WHERE issue_timestamp::date BETWEEN %s AND %s ORDER BY issue_timestamp, invoice_id",
            (start, end),
        )]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Invoice]:
        _page(limit, offset)
        return [_invoice(row) for row in self.db.fetch_all(
            "SELECT * FROM truelock.invoices ORDER BY issue_timestamp, invoice_id LIMIT %s OFFSET %s", (limit, offset)
        )]


class _PaymentRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, payment_id: str) -> Payment | None:
        row = self.db.fetch_one(
            """
            SELECT pc.payment_id, pd.related_document_uuid, pc.payment_date, pc.payment_amount,
                   pc.payment_form, pc.currency, pd.previous_balance, pd.remaining_balance
            FROM truelock.payment_complements pc JOIN truelock.payment_documents pd ON pd.payment_id = pc.payment_id
            WHERE pc.payment_id::text = %s LIMIT 1
            """,
            (payment_id,),
        )
        return _payment(row) if row else None

    def list_for_invoice(self, invoice_uuid: str) -> list[Payment]:
        return [_payment(row) for row in self.db.fetch_all(
            """
            SELECT pc.payment_id, pd.related_document_uuid, pc.payment_date, pc.payment_amount,
                   pc.payment_form, pc.currency, pd.previous_balance, pd.remaining_balance
            FROM truelock.payment_complements pc JOIN truelock.payment_documents pd ON pd.payment_id = pc.payment_id
            WHERE pd.related_document_uuid = %s ORDER BY pc.payment_date, pc.payment_id
            """,
            (invoice_uuid,),
        )]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Payment]:
        _page(limit, offset)
        return [_payment(row) for row in self.db.fetch_all(
            """
            SELECT pc.payment_id, pd.related_document_uuid, pc.payment_date, pc.payment_amount,
                   pc.payment_form, pc.currency, pd.previous_balance, pd.remaining_balance
            FROM truelock.payment_complements pc JOIN truelock.payment_documents pd ON pd.payment_id = pc.payment_id
            ORDER BY pc.payment_date, pc.payment_id LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )]


class _TransactionRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, transaction_id: str) -> Transaction | None:
        row = self.db.fetch_one(_transaction_query("bt.bank_transaction_id::text = %s"), (transaction_id,))
        return _transaction(row) if row else None

    def list_outgoing(self, account_no: str) -> list[Transaction]:
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query("origin.account_number = %s"), (account_no,)
        )]

    def list_incoming(self, account_no: str) -> list[Transaction]:
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query("destination.account_number = %s"), (account_no,)
        )]

    def list_for_payment(self, payment_id: str) -> list[Transaction]:
        return []

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Transaction]:
        _page(limit, offset)
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query("TRUE") + " LIMIT %s OFFSET %s", (limit, offset)
        )]


def _transaction_query(where: str) -> str:
    return f"""
        SELECT bt.bank_transaction_id, origin.account_number AS from_account,
               destination.account_number AS to_account, bt.booked_at::date AS transaction_date,
               bt.amount
        FROM truelock.bank_transactions bt
        JOIN truelock.bank_accounts origin ON origin.bank_account_id = bt.origin_bank_account_id
        JOIN truelock.bank_accounts destination ON destination.bank_account_id = bt.destination_bank_account_id
        WHERE {where}
        ORDER BY bt.booked_at, bt.bank_transaction_id
    """


def _page(limit: int, offset: int) -> None:
    if limit < 0 or offset < 0:
        raise ValueError("limit and offset must not be negative")


def _number(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def _entity(row: dict[str, Any]) -> Entity:
    return Entity(
        id=str(row["entity_id"]),
        name=row["canonical_name"],
        entity_type="individual" if row["entity_type"] == "PERSON" else "company",
        rfc=row["rfc"],
    )


def _provider(row: dict[str, Any]) -> Provider:
    statuses = {"PRESUNTO": "PRESUMED", "DEFINITIVO": "DEFINITIVE", "DESVIRTUADO": "INVALIDATED", "SENTENCIA_FAVORABLE": "FAVORABLE_JUDGMENT"}
    return Provider(
        rfc=row["rfc"],
        name=row["name"],
        address=row.get("address"),
        efos_status=EfosStatus(statuses.get(row.get("sat_status"), "UNKNOWN")),
        efos_listed_date=row.get("snapshot_date") if row.get("sat_status") else None,
    )


def _account(row: dict[str, Any]) -> Account:
    return Account(account_no=row["account_number"] or row["masked_account"], entity_id=str(row["entity_id"]), bank=row["bank_name"])


def _invoice(row: dict[str, Any]) -> Invoice:
    return Invoice(
        uuid=row["uuid"],
        provider_rfc=row["rfc_issuer"],
        receiver_rfc=row["rfc_receiver"],
        issue_date=row["issue_timestamp"].date(),
        amount=_number(row["total"]),
        version=row["version"] or "4.0",
        subtotal=_number(row["subtotal"]),
        taxes=_number(row["tax_total"]),
        currency=row["currency"],
        payment_method=row["payment_method"],
        payment_form=row["payment_form"],
        cfdi_type=row["cfdi_type"],
    )


def _payment(row: dict[str, Any]) -> Payment:
    return Payment(
        id=str(row["payment_id"]),
        related_invoice_uuid=row["related_document_uuid"],
        payment_date=row["payment_date"].date(),
        amount=_number(row["payment_amount"]),
        payment_form=row["payment_form"],
        currency=row["currency"],
        previous_balance=_number(row["previous_balance"]) if row["previous_balance"] is not None else None,
        remaining_balance=_number(row["remaining_balance"]) if row["remaining_balance"] is not None else None,
    )


def _transaction(row: dict[str, Any]) -> Transaction:
    return Transaction(
        id=str(row["bank_transaction_id"]),
        from_account=row["from_account"],
        to_account=row["to_account"],
        transaction_date=row["transaction_date"],
        amount=_number(row["amount"]),
    )


def _row_json(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _number(value) if isinstance(value, Decimal) else str(value) if key.endswith("_id") and value is not None else value for key, value in row.items()}


def _evidence_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": str(row["evidence_id"]),
        "type": row["evidence_type"],
        "source_id": str(row["record_id"]),
        "source_file_id": str(row["source_file_id"]) if row["source_file_id"] else None,
        "source_locator": row["source_locator"],
        "facts": row["facts"],
        "role": row["role"],
    }


def _lead_dict(row: dict[str, Any]) -> dict[str, Any]:
    detector_codes = row["detector_codes"] or []
    return {
        "lead_id": str(row["lead_id"]),
        "entity_id": str(row["entity_id"]) if row["entity_id"] else "",
        "detector_id": detector_codes[0] if detector_codes else "PERSISTED_LEAD",
        "reason": row["reason_summary"],
        "risk_score": _number(row["risk_score"]) / 100,
        "signals": detector_codes,
        "status": row["status"],
        "display_id": row["display_id"],
        "title": row["title"],
    }


def _step_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": str(row["step_id"]),
        "thread_id": str(row["thread_id"]),
        "sequence": row["sequence"],
        "action": row["action"],
        "tool": row["tool_name"],
        "reason": row["reason_summary"],
        "inputs": row["tool_inputs"],
        "result": row["result_summary"],
        "provenance": row["provenance"],
        "errors": row["errors"],
        "decision": row["decision"],
        "duration_ms": row["duration_ms"],
        "evidence_ids": [str(value) for value in row["input_evidence_ids"] + row["result_evidence_ids"]],
    }
