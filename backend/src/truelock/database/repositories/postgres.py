"""PostgreSQL repository implementations for the production TrueLock path.

The public repository protocols remain intentionally small.  This module owns
the SQL boundary, uses a shared connection pool, and maps the canonical
``truelock`` schema back to the Pydantic records consumed by the detector and
agent layers.  All statements are parameterized.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterator
from pathlib import Path
from urllib.parse import urlparse

from truelock.domain.models import Account, EfosStatus, Entity, Invoice, Payment, Provider, Transaction
from truelock.domain.models.investigation import (
    Case,
    Evidence,
    InvestigationStep,
    Lead,
    LeadStatus,
)

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def validate_database_url(value: str) -> str:
    """Reject malformed or non-PostgreSQL URLs before opening a pool."""
    parsed = urlparse(value)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
    return value


def deterministic_uuid(key: str) -> uuid.UUID:
    """Stable UUID derived from an external business key."""
    return uuid.uuid5(_NAMESPACE, key)


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

    def persist_operational_event(self, event: dict[str, Any]) -> None:
        """Persist an observability event without requiring a UUID case row."""
        attributes = dict(event.get("attributes") or {})
        if event.get("step_id"):
            attributes["step_id"] = event["step_id"]
        if event.get("message"):
            attributes["message"] = event["message"]
        if event.get("result_hash"):
            attributes["result_hash"] = event["result_hash"]
        attributes["external_case_key"] = event.get("case_id")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO truelock.operational_events (
                    event_type, attributes, external_case_key
                ) VALUES (%s, %s::jsonb, %s)
                """,
                (
                    str(event.get("event_type") or "investigation"),
                    json.dumps(attributes, default=str),
                    str(event.get("case_id") or ""),
                ),
            )

    def list_operational_events(
        self, external_case_key: str, *, offset: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT occurred_at, event_type, attributes, external_case_key
            FROM truelock.operational_events
            WHERE external_case_key = %s
            ORDER BY occurred_at ASC
            OFFSET %s LIMIT %s
            """,
            (external_case_key, max(0, offset), max(1, min(limit, 500))),
        )
        events: list[dict[str, Any]] = []
        for row in rows:
            attrs = row.get("attributes") or {}
            if isinstance(attrs, str):
                attrs = json.loads(attrs)
            events.append(
                {
                    "timestamp": row["occurred_at"].isoformat().replace("+00:00", "Z")
                    if hasattr(row["occurred_at"], "isoformat")
                    else str(row["occurred_at"]),
                    "case_id": row.get("external_case_key") or external_case_key,
                    "message": attrs.get("message", ""),
                    "step_id": attrs.get("step_id"),
                    "event_type": row["event_type"],
                    "attributes": attrs,
                    "result_hash": attrs.get("result_hash"),
                }
            )
        return events

    def canonical_case_id(self) -> uuid.UUID | None:
        row = self.fetch_one(
            """
            SELECT case_id FROM truelock.cases
            WHERE display_id = 'CASE-DEMO-001'
            ORDER BY opened_at LIMIT 1
            """
        )
        return row["case_id"] if row else None

    def clear_analysis(self, case_id: uuid.UUID | str | None = None) -> dict[str, int]:
        """Remove investigation artifacts for a case; keep financial source data."""
        target = case_id or self.canonical_case_id()
        if not target:
            raise ValueError("No canonical case found; run seed_demo.sh first")

        counts: dict[str, int] = {}
        with self.connection() as conn, conn.cursor() as cur:
            # Demo reset may delete append-only audit rows inside one transaction.
            cur.execute(
                "ALTER TABLE truelock.investigation_steps DISABLE TRIGGER investigation_steps_append_only"
            )
            cur.execute("ALTER TABLE truelock.evidence DISABLE TRIGGER evidence_append_only")
            cur.execute(
                "ALTER TABLE truelock.case_file_versions DISABLE TRIGGER case_file_versions_append_only"
            )
            try:
                def _count_delete(label: str, sql: str, params: tuple[Any, ...] = (target,)) -> None:
                    cur.execute(sql, params)
                    counts[label] = cur.rowcount

                _count_delete(
                    "case_questions",
                    "DELETE FROM truelock.case_questions WHERE case_id = %s",
                )
                _count_delete(
                    "findings",
                    "DELETE FROM truelock.findings WHERE case_id = %s",
                )
                _count_delete(
                    "exposure_calculations",
                    "DELETE FROM truelock.exposure_calculations WHERE case_id = %s",
                )
                _count_delete(
                    "investigation_steps",
                    "DELETE FROM truelock.investigation_steps WHERE case_id = %s",
                )
                _count_delete(
                    "investigation_threads",
                    "DELETE FROM truelock.investigation_threads WHERE case_id = %s",
                )
                _count_delete(
                    "investigations",
                    "DELETE FROM truelock.investigations WHERE case_id = %s",
                )
                cur.execute(
                    """
                    DELETE FROM truelock.lead_anomalies
                    WHERE lead_id IN (SELECT lead_id FROM truelock.leads WHERE case_id = %s)
                    """,
                    (target,),
                )
                counts["lead_anomalies"] = cur.rowcount
                _count_delete("leads", "DELETE FROM truelock.leads WHERE case_id = %s")
                _count_delete("anomalies", "DELETE FROM truelock.anomalies WHERE case_id = %s")
                _count_delete(
                    "detector_runs",
                    "DELETE FROM truelock.detector_runs WHERE case_id = %s",
                )
                _count_delete("evidence", "DELETE FROM truelock.evidence WHERE case_id = %s")
                _count_delete(
                    "case_file_versions",
                    "DELETE FROM truelock.case_file_versions WHERE case_id = %s",
                )
                _count_delete(
                    "operational_events",
                    "DELETE FROM truelock.operational_events WHERE case_id = %s",
                )
                cur.execute(
                    """
                    DELETE FROM truelock.operational_events
                    WHERE external_case_key = ANY(%s::text[])
                    """,
                    (["DEMO", "IMPORT", "OPS"],),
                )
                counts["operational_events_external"] = cur.rowcount
            finally:
                cur.execute(
                    "ALTER TABLE truelock.investigation_steps ENABLE TRIGGER investigation_steps_append_only"
                )
                cur.execute("ALTER TABLE truelock.evidence ENABLE TRIGGER evidence_append_only")
                cur.execute(
                    "ALTER TABLE truelock.case_file_versions ENABLE TRIGGER case_file_versions_append_only"
                )
        return counts

    def purge_case_financial_data(
        self, case_id: uuid.UUID | str | None = None, *, keep_case: bool = False
    ) -> dict[str, int]:
        """Delete all financial/master rows for a case (after clear_analysis)."""
        target = case_id or self.canonical_case_id()
        if not target:
            raise ValueError("No canonical case found; run seed_demo.sh first")

        counts: dict[str, int] = {}
        with self.connection() as conn, conn.cursor() as cur:
            def _count_delete(label: str, sql: str, params: tuple[Any, ...] = (target,)) -> None:
                cur.execute(sql, params)
                counts[label] = cur.rowcount

            _count_delete(
                "reconciliation_matches",
                "DELETE FROM truelock.reconciliation_matches WHERE case_id = %s",
            )
            _count_delete(
                "ledger_entries",
                "DELETE FROM truelock.ledger_entries WHERE case_id = %s",
            )
            _count_delete(
                "bank_transactions",
                "DELETE FROM truelock.bank_transactions WHERE case_id = %s",
            )
            cur.execute(
                """
                DELETE FROM truelock.payment_documents
                WHERE payment_id IN (
                    SELECT payment_id FROM truelock.payment_complements WHERE case_id = %s
                )
                """,
                (target,),
            )
            counts["payment_documents"] = cur.rowcount
            _count_delete(
                "payment_complements",
                "DELETE FROM truelock.payment_complements WHERE case_id = %s",
            )
            cur.execute(
                """
                DELETE FROM truelock.invoice_relationships
                WHERE invoice_id IN (SELECT invoice_id FROM truelock.invoices WHERE case_id = %s)
                   OR related_invoice_id IN (SELECT invoice_id FROM truelock.invoices WHERE case_id = %s)
                """,
                (target, target),
            )
            counts["invoice_relationships"] = cur.rowcount
            cur.execute(
                """
                DELETE FROM truelock.invoice_concepts
                WHERE invoice_id IN (SELECT invoice_id FROM truelock.invoices WHERE case_id = %s)
                """,
                (target,),
            )
            counts["invoice_concepts"] = cur.rowcount
            _count_delete("invoices", "DELETE FROM truelock.invoices WHERE case_id = %s")
            _count_delete("suppliers", "DELETE FROM truelock.suppliers WHERE case_id = %s")
            cur.execute(
                """
                DELETE FROM truelock.entity_bank_accounts
                WHERE entity_id IN (SELECT entity_id FROM truelock.entities WHERE case_id = %s)
                   OR bank_account_id IN (
                        SELECT bank_account_id FROM truelock.bank_accounts WHERE case_id = %s
                   )
                """,
                (target, target),
            )
            counts["entity_bank_accounts"] = cur.rowcount
            _count_delete(
                "bank_accounts",
                "DELETE FROM truelock.bank_accounts WHERE case_id = %s",
            )
            _count_delete(
                "entity_relationships",
                "DELETE FROM truelock.entity_relationships WHERE case_id = %s",
            )
            _count_delete(
                "entity_identifiers",
                "DELETE FROM truelock.entity_identifiers WHERE case_id = %s",
            )
            _count_delete("entities", "DELETE FROM truelock.entities WHERE case_id = %s")
            cur.execute(
                """
                DELETE FROM truelock.sat_69b_records
                WHERE sat_snapshot_id IN (
                    SELECT sat_snapshot_id FROM truelock.sat_69b_snapshots
                    WHERE source_file_id IN (
                        SELECT source_file_id FROM truelock.source_files WHERE case_id = %s
                    )
                )
                """,
                (target,),
            )
            counts["sat_69b_records"] = cur.rowcount
            cur.execute(
                """
                DELETE FROM truelock.sat_69b_snapshots
                WHERE source_file_id IN (
                    SELECT source_file_id FROM truelock.source_files WHERE case_id = %s
                )
                """,
                (target,),
            )
            counts["sat_69b_snapshots"] = cur.rowcount
            _count_delete(
                "data_coverage",
                "DELETE FROM truelock.data_coverage WHERE case_id = %s",
            )
            _count_delete(
                "case_source_files",
                "DELETE FROM truelock.case_source_files WHERE case_id = %s",
            )
            cur.execute(
                """
                DELETE FROM truelock.ingest_rejections
                WHERE source_file_id IN (
                    SELECT source_file_id FROM truelock.source_files WHERE case_id = %s
                )
                """,
                (target,),
            )
            counts["ingest_rejections"] = cur.rowcount
            _count_delete(
                "source_files",
                "DELETE FROM truelock.source_files WHERE case_id = %s",
            )
            if keep_case:
                return counts

            cur.execute(
                "SELECT organization_id FROM truelock.cases WHERE case_id = %s",
                (target,),
            )
            org_row = cur.fetchone()
            org_id = org_row["organization_id"] if org_row else None
            _count_delete("cases", "DELETE FROM truelock.cases WHERE case_id = %s")
            if org_id is not None:
                cur.execute(
                    """
                    DELETE FROM truelock.organizations org
                    WHERE organization_id = %s
                      AND NOT EXISTS (
                        SELECT 1 FROM truelock.cases c WHERE c.organization_id = org.organization_id
                      )
                    """,
                    (org_id,),
                )
                counts["organizations"] = cur.rowcount
        return counts

    def ensure_canonical_case(self) -> uuid.UUID:
        """Create empty CASE-DEMO-001 shell when the workspace was wiped."""
        existing = self.canonical_case_id()
        if existing:
            return existing
        org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        case_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO truelock.organizations (organization_id, legal_name, rfc)
                VALUES (%s, 'Empresa Operadora Nacional SA de CV', 'EDE180101AA1')
                ON CONFLICT (organization_id) DO NOTHING
                """,
                (org_id,),
            )
            cur.execute(
                """
                INSERT INTO truelock.cases (
                    case_id, organization_id, display_id, title, status, base_currency, metadata
                ) VALUES (
                    %s, %s, 'CASE-DEMO-001', 'Empty workspace', 'CREATED', 'MXN',
                    '{"fixture":"empty-workspace"}'::jsonb
                )
                ON CONFLICT (case_id) DO NOTHING
                """,
                (case_id, org_id),
            )
        return case_id

    def wipe_workspace(self) -> dict[str, Any]:
        """Remove all analysis + financial rows; keep an empty CASE-DEMO-001 shell."""
        target = self.canonical_case_id()
        analysis: dict[str, int] = {}
        financial: dict[str, int] = {}
        if target:
            analysis = self.clear_analysis(target)
            financial = self.purge_case_financial_data(target, keep_case=True)
        case_id = self.ensure_canonical_case()
        return {
            "analysis": analysis,
            "financial": financial,
            "case_id": str(case_id),
        }

    def reseed_canonical_demo(self, seed_path: Path | None = None) -> None:
        """Load ``database/seeds/001_demo.sql`` after a full purge."""
        path = seed_path or (Path(__file__).resolve().parents[5] / "database" / "seeds" / "001_demo.sql")
        if not path.is_file():
            raise FileNotFoundError(f"Demo seed SQL not found: {path}")
        sql = path.read_text(encoding="utf-8")
        cleaned = "\n".join(
            line
            for line in sql.splitlines()
            if line.strip().upper() not in {"BEGIN;", "COMMIT;"}
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(cleaned)

    def reset_canonical_demo(self, seed_path: Path | None = None) -> dict[str, Any]:
        """Full wipe of CASE-DEMO-001 (threads + data) and reseed from SQL.

        The SQL seed includes completed investigation fixtures for DB tests; those
        are stripped after reseed so the live demo starts with a clean analysis
        surface (financial data only, then detectors re-run by the caller).
        """
        target = self.canonical_case_id()
        analysis: dict[str, int] = {}
        financial: dict[str, int] = {}
        if target:
            analysis = self.clear_analysis(target)
            financial = self.purge_case_financial_data(target)
        self.reseed_canonical_demo(seed_path)
        seeded_case = self.canonical_case_id()
        post_seed_analysis: dict[str, int] = {}
        if seeded_case:
            post_seed_analysis = self.clear_analysis(seeded_case)
        return {
            "analysis": analysis,
            "financial": financial,
            "post_seed_analysis": post_seed_analysis,
            "case_id": str(seeded_case or ""),
        }

    def dataset_fingerprint(self, case_id: uuid.UUID | str | None = None) -> str:
        """Hash of source-file digests for investigation idempotency."""
        target = case_id or self.canonical_case_id()
        if not target:
            return "no-case"
        rows = self.fetch_all(
            """
            SELECT sha256 FROM truelock.source_files
            WHERE case_id = %s ORDER BY sha256
            """,
            (target,),
        )
        material = "|".join(row["sha256"] for row in rows) or "empty"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def list_lead_records(self) -> list[Lead]:
        rows = self.fetch_all(
            """
            SELECT l.lead_id, l.display_id, l.external_lead_key, l.title, l.risk_score, l.status,
                   l.reason_summary,
                   (array_agg(le.entity_id::text ORDER BY le.entity_id::text)
                     FILTER (WHERE le.entity_id IS NOT NULL))[1] AS entity_id,
                   coalesce(array_agg(DISTINCT a.detector_code)
                     FILTER (WHERE a.detector_code IS NOT NULL), ARRAY[]::text[]) AS detector_codes
            FROM truelock.leads l
            LEFT JOIN truelock.lead_entities le ON le.lead_id = l.lead_id
            LEFT JOIN truelock.lead_anomalies la ON la.lead_id = l.lead_id
            LEFT JOIN truelock.anomalies a ON a.anomaly_id = la.anomaly_id
            GROUP BY l.lead_id, l.display_id, l.external_lead_key, l.title, l.risk_score, l.status,
                     l.reason_summary, l.created_at
            ORDER BY l.risk_score DESC, l.created_at
            """
        )
        return [_lead_model(row) for row in rows]

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

    def get_lead_record(self, lead_id: str) -> Lead | None:
        for lead in self.list_lead_records():
            if lead.lead_id == lead_id:
                return lead
        row = self.fetch_one(
            """
            SELECT l.lead_id, l.display_id, l.external_lead_key, l.title, l.risk_score, l.status,
                   l.reason_summary, NULL::text AS entity_id, ARRAY[]::text[] AS detector_codes
            FROM truelock.leads l
            WHERE l.lead_id::text = %s OR l.display_id = %s OR l.external_lead_key = %s
            LIMIT 1
            """,
            (lead_id, lead_id, lead_id),
        )
        return _lead_model(row) if row else None

    def resolve_lead_uuid(self, lead_id: str) -> uuid.UUID | None:
        row = self.fetch_one(
            """
            SELECT lead_id FROM truelock.leads
            WHERE lead_id::text = %s OR display_id = %s OR external_lead_key = %s
            LIMIT 1
            """,
            (lead_id, lead_id, lead_id),
        )
        return row["lead_id"] if row else None

    def upsert_detector_leads(self, leads: list[Lead], *, case_id: uuid.UUID | str | None = None) -> list[Lead]:
        """Persist detector output idempotently by external_lead_key."""
        target = case_id or self.canonical_case_id()
        if not target:
            raise ValueError("No case available for lead persistence")
        with self.connection() as conn, conn.cursor() as cur:
            for lead in leads:
                lead_uuid = deterministic_uuid(f"lead:{lead.lead_id}")
                entity_uuid = self._resolve_entity_uuid(cur, target, lead.entity_id)
                status = _lead_status_to_db(lead.status)
                cur.execute(
                    """
                    SELECT lead_id FROM truelock.leads
                    WHERE case_id = %s AND (external_lead_key = %s OR display_id = %s)
                    LIMIT 1
                    """,
                    (target, lead.lead_id, lead.lead_id[:64]),
                )
                existing = cur.fetchone()
                if existing:
                    persisted = existing["lead_id"]
                    cur.execute(
                        """
                        UPDATE truelock.leads SET
                            external_lead_key = %s,
                            title = %s,
                            risk_score = %s,
                            reason_summary = %s,
                            updated_at = clock_timestamp()
                        WHERE lead_id = %s
                        """,
                        (
                            lead.lead_id,
                            lead.reason[:200],
                            round(float(lead.risk_score) * 100, 2),
                            lead.reason,
                            persisted,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO truelock.leads (
                            lead_id, case_id, display_id, external_lead_key, title, risk_score,
                            risk_score_version, priority, status, reason_summary
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, 'detector-v1', %s, %s, %s
                        )
                        RETURNING lead_id
                        """,
                        (
                            lead_uuid,
                            target,
                            lead.lead_id[:64],
                            lead.lead_id,
                            lead.reason[:200],
                            round(float(lead.risk_score) * 100, 2),
                            _priority_for_score(lead.risk_score),
                            status,
                            lead.reason,
                        ),
                    )
                    persisted = cur.fetchone()["lead_id"]
                if entity_uuid:
                    cur.execute(
                        """
                        INSERT INTO truelock.lead_entities (lead_id, entity_id, role)
                        VALUES (%s, %s, 'SUBJECT')
                        ON CONFLICT DO NOTHING
                        """,
                        (persisted, entity_uuid),
                    )
        return self.list_lead_records()

    def existing_investigation_for_lead(
        self, lead_id: str, *, dataset_fingerprint: str | None = None
    ) -> dict[str, Any] | None:
        fingerprint = dataset_fingerprint or self.dataset_fingerprint()
        row = self.fetch_one(
            """
            SELECT c.display_id, i.dataset_fingerprint
            FROM truelock.investigations i
            JOIN truelock.cases c ON c.case_id = i.case_id
            JOIN truelock.leads l ON l.lead_id = i.lead_id
            WHERE l.lead_id::text = %s OR l.display_id = %s OR l.external_lead_key = %s
            ORDER BY i.created_at DESC LIMIT 1
            """,
            (lead_id, lead_id, lead_id),
        )
        if not row:
            return None
        if row.get("dataset_fingerprint") and row["dataset_fingerprint"] != fingerprint:
            return None
        details = self.investigation_details(row["display_id"])
        if not details:
            return None
        # Do not reuse empty/failed shells — allow a fresh investigation.
        if not details.get("evidence"):
            return None
        return details

    def investigation_details(self, case_reference: str) -> dict[str, Any] | None:
        """Build the API investigation payload entirely from persisted records."""
        case_row = self.fetch_one(
            """
            SELECT c.case_id, c.display_id, c.title, c.metadata
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
            ORDER BY t.created_at DESC LIMIT 1
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
        meta = case_row.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        agent_status = str(meta.get("agent_status") or "")
        if finding:
            status = "SUBSTANTIATED"
            amount = _number(finding["supported_exposure_mxn"])
            hypothesis = finding["claim"]
            confidence = finding["confidence_label"]
            limitations = finding["limitations"] or []
        elif thread and thread["status"] == "SUPPORTED":
            status = "SUBSTANTIATED"
            amount = float(meta.get("amount_involved") or 0)
            hypothesis = thread["hypothesis_claim"]
            confidence = "HIGH"
            limitations = []
        elif agent_status:
            status = agent_status
            amount = float(meta.get("amount_involved") or 0)
            hypothesis = meta.get("hypothesis") or (thread["hypothesis_claim"] if thread else case_row["title"])
            confidence = "MEDIUM"
            limitations = []
        else:
            status = "INSUFFICIENT_EVIDENCE" if not evidence else "UNSUBSTANTIATED"
            amount = 0.0
            hypothesis = thread["hypothesis_claim"] if thread else case_row["title"]
            confidence = "MEDIUM"
            limitations = []
        if finding is None and thread and thread["status"] == "INSUFFICIENT_EVIDENCE":
            status = "INSUFFICIENT_EVIDENCE"
        case_payload = {
            "case_id": case_row["display_id"],
            "status": status,
            "hypothesis": hypothesis,
            "providers_involved": [],
            "amount_involved": amount,
            "supporting_evidence": [str(row["evidence_id"]) for row in evidence],
            "confidence_level": confidence,
            "limitations": limitations,
            "citations": [],
        }
        return {
            "case": case_payload,
            "steps": [_step_dict(row) for row in steps],
            "evidence": [_evidence_dict(row) for row in evidence],
            "finding": _row_json(finding) if finding else None,
            "thread_id": str(thread["thread_id"]) if thread else None,
        }

    def persist_investigation_result(
        self,
        *,
        lead: Lead,
        case: Case,
        steps: list[InvestigationStep],
        evidence: list[Evidence],
        idempotency_key: str,
        dataset_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """Write one investigation atomically and return the read-model payload."""
        case_uuid = self.canonical_case_id()
        if not case_uuid:
            raise ValueError("No case available for investigation persistence")
        fingerprint = dataset_fingerprint or self.dataset_fingerprint(case_uuid)
        lead_uuid = self.resolve_lead_uuid(lead.lead_id)
        if not lead_uuid:
            self.upsert_detector_leads([lead], case_id=case_uuid)
            lead_uuid = self.resolve_lead_uuid(lead.lead_id)
        if not lead_uuid:
            raise ValueError(f"Unable to persist lead {lead.lead_id}")

        existing = self.fetch_one(
            """
            SELECT c.display_id FROM truelock.investigations i
            JOIN truelock.cases c ON c.case_id = i.case_id
            WHERE i.case_id = %s AND i.idempotency_key = %s
            """,
            (case_uuid, idempotency_key),
        )
        if existing:
            return self.investigation_details(existing["display_id"])  # type: ignore[return-value]

        investigation_id = deterministic_uuid(f"investigation:{idempotency_key}")
        thread_id = deterministic_uuid(f"thread:{idempotency_key}")
        now = datetime.now(timezone.utc)
        thread_status = _case_status_to_thread(case.status)
        step_decision_map = {
            "FOLLOW": "CONTINUE",
            "DISCARD": "REJECT",
            "ESCALATE": "ESCALATE",
            "CONCLUDE": "SUPPORT" if case.status == "SUBSTANTIATED" else "STOP",
        }

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE truelock.leads
                SET status = 'INVESTIGATING', updated_at = clock_timestamp()
                WHERE lead_id = %s
                """,
                (lead_uuid,),
            )
            cur.execute(
                """
                INSERT INTO truelock.investigations (
                    investigation_id, case_id, lead_id, status, model_provider, model_name,
                    tool_calls_used, started_at, completed_at, idempotency_key, dataset_fingerprint
                ) VALUES (
                    %s, %s, %s, 'COMPLETED', 'gemini-or-offline', 'investigator',
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    investigation_id,
                    case_uuid,
                    lead_uuid,
                    len(steps),
                    now,
                    now,
                    idempotency_key,
                    fingerprint,
                ),
            )
            cur.execute(
                """
                INSERT INTO truelock.investigation_threads (
                    thread_id, investigation_id, case_id, display_id, scheme_code,
                    hypothesis_claim, status, tool_calls_used, last_new_evidence_sequence,
                    outcome_reason, created_at, closed_at
                ) VALUES (
                    %s, %s, %s, 'T-AUTO', 'ROUND_TRIPPING', %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    thread_id,
                    investigation_id,
                    case_uuid,
                    case.hypothesis,
                    thread_status,
                    len(steps),
                    len(steps) or None,
                    case.status,
                    now,
                    now,
                ),
            )

            evidence_id_map: dict[str, uuid.UUID] = {}
            for item in evidence:
                evidence_uuid = deterministic_uuid(f"evidence:{idempotency_key}:{item.evidence_id}")
                evidence_id_map[item.evidence_id] = evidence_uuid
                record_uuid = self._resolve_record_uuid(cur, case_uuid, item.source_id)
                evidence_type = _evidence_type_to_db(item.type)
                facts = {
                    "claim": item.claim,
                    "strength": str(getattr(item.strength, "value", item.strength)),
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "domain_evidence_id": item.evidence_id,
                }
                cur.execute(
                    """
                    INSERT INTO truelock.evidence (
                        evidence_id, case_id, evidence_type, record_id, source_file_id,
                        source_locator, source_record_sha256, facts, created_by
                    ) VALUES (
                        %s, %s, %s, %s, NULL, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        evidence_uuid,
                        case_uuid,
                        evidence_type,
                        record_uuid,
                        item.source_id,
                        item.record_hash if item.record_hash and len(item.record_hash) == 64 else None,
                        json.dumps(facts),
                        item.gathered_by_step_id or "investigator",
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO truelock.thread_evidence (thread_id, evidence_id, role, assertion_code)
                    VALUES (%s, %s, 'SUPPORTING', %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (thread_id, evidence_uuid, item.type if isinstance(item.type, str) else item.type.value),
                )

            for index, step in enumerate(steps, start=1):
                step_uuid = deterministic_uuid(f"step:{idempotency_key}:{step.step_id}")
                decision = step_decision_map.get(
                    str(getattr(step.decision, "value", step.decision)), "CONTINUE"
                )
                cur.execute(
                    """
                    INSERT INTO truelock.investigation_steps (
                        step_id, case_id, investigation_id, thread_id, sequence, action, tool_name,
                        reason_summary, tool_inputs, result_summary, provenance, errors, decision,
                        started_at, completed_at, duration_ms
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, '[]'::jsonb,
                        %s, %s, %s, 0
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        step_uuid,
                        case_uuid,
                        investigation_id,
                        thread_id,
                        index,
                        step.action,
                        step.tool,
                        step.reason,
                        json.dumps(step.inputs or {}),
                        json.dumps({"result_refs": step.result_refs, "next_action": step.next_action}),
                        json.dumps({"domain_step_id": step.step_id}),
                        decision,
                        now,
                        now,
                    ),
                )
                for ref in step.result_refs:
                    mapped = evidence_id_map.get(ref)
                    if mapped:
                        cur.execute(
                            """
                            INSERT INTO truelock.investigation_step_result_evidence (step_id, evidence_id)
                            VALUES (%s, %s) ON CONFLICT DO NOTHING
                            """,
                            (step_uuid, mapped),
                        )

            lead_db_status = "SUPPORTED" if case.status == "SUBSTANTIATED" else (
                "INSUFFICIENT_EVIDENCE" if case.status == "INSUFFICIENT_EVIDENCE" else "REJECTED"
            )
            if case.status == "SUBSTANTIATED":
                exposure_id = deterministic_uuid(f"exposure:{idempotency_key}")
                finding_id = deterministic_uuid(f"finding:{idempotency_key}")
                root_amount = float(case.amount_involved or 0)
                cur.execute(
                    """
                    INSERT INTO truelock.exposure_calculations (
                        exposure_calculation_id, case_id, calculation_version,
                        allocation_method, base_currency, parameters, limitations
                    ) VALUES (%s, %s, 'agent-v1', 'root_flow', 'MXN', %s::jsonb, %s::jsonb)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        exposure_id,
                        case_uuid,
                        json.dumps({"amount_involved": root_amount}),
                        json.dumps(list(case.limitations or [])),
                    ),
                )
                root_tx = None
                for item in evidence:
                    if str(getattr(item.type, "value", item.type)) in {"TRANSACTION", "BANK_TRANSACTION"}:
                        root_tx = self._resolve_record_uuid(cur, case_uuid, item.source_id)
                        break
                if root_tx is None:
                    root_tx = deterministic_uuid(f"exposure-root:{idempotency_key}")
                cur.execute(
                    """
                    INSERT INTO truelock.exposure_components (
                        exposure_component_id, exposure_calculation_id, root_flow_id,
                        component_type, source_record_type, source_record_id,
                        root_bank_transaction_id, amount_mxn, path_sequence, is_supported
                    ) VALUES (
                        %s, %s, %s, 'ROOT', 'BANK_TRANSACTION', %s, %s, %s, 0, true
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        deterministic_uuid(f"exposure-comp:{idempotency_key}"),
                        exposure_id,
                        f"root:{idempotency_key}",
                        root_tx,
                        root_tx,
                        root_amount,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO truelock.findings (
                        finding_id, case_id, thread_id, display_id, scheme_code, claim,
                        status, confidence_label, exposure_calculation_id,
                        supported_exposure_mxn, coverage_sufficient, limitations
                    ) VALUES (
                        %s, %s, %s, %s, 'ROUND_TRIPPING', %s,
                        'SUPPORTED', %s, %s, %s, true, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        finding_id,
                        case_uuid,
                        thread_id,
                        f"F-{lead.lead_id}"[:64],
                        case.hypothesis,
                        case.confidence_level or "HIGH",
                        exposure_id,
                        root_amount,
                        json.dumps(list(case.limitations or [])),
                    ),
                )
                for domain_id, evidence_uuid in evidence_id_map.items():
                    cur.execute(
                        """
                        INSERT INTO truelock.finding_evidence (finding_id, evidence_id, role)
                        VALUES (%s, %s, 'SUPPORTING')
                        ON CONFLICT DO NOTHING
                        """,
                        (finding_id, evidence_uuid),
                    )

            cur.execute(
                """
                UPDATE truelock.leads
                SET status = %s, updated_at = clock_timestamp()
                WHERE lead_id = %s
                """,
                (lead_db_status, lead_uuid),
            )
            cur.execute(
                """
                UPDATE truelock.cases
                SET status = 'COMPLETED',
                    metadata = metadata || %s::jsonb
                WHERE case_id = %s
                """,
                (
                    json.dumps(
                        {
                            "last_case_id": case.case_id,
                            "agent_status": case.status,
                            "amount_involved": case.amount_involved,
                            "hypothesis": case.hypothesis,
                        }
                    ),
                    case_uuid,
                ),
            )

        return self.investigation_details("CASE-DEMO-001")  # type: ignore[return-value]

    def find_source_file_by_hash(self, case_id: uuid.UUID | str, sha256: str) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT source_file_id, case_id, original_filename, dataset_kind, sha256,
                   parser_name, parser_version, status, record_count, rejected_count, metadata
            FROM truelock.source_files
            WHERE case_id = %s AND sha256 = %s
            """,
            (case_id, sha256),
        )

    def list_ingest_rejections(self, source_file_id: uuid.UUID | str) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT source_locator, error_code, error_message
            FROM truelock.ingest_rejections
            WHERE source_file_id = %s
            ORDER BY rejected_at, source_locator
            """,
            (source_file_id,),
        )

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
        return {
            "case_id": case["display_id"],
            "nodes": [_row_json(row) for row in entities],
            "edges": [_row_json(row) for row in edges],
        }

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
            question_id = cur.fetchone()["question_id"]
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

    def _resolve_entity_uuid(self, cur: Any, case_id: uuid.UUID | str, entity_ref: str) -> uuid.UUID | None:
        cur.execute(
            """
            SELECT entity_id FROM truelock.entities
            WHERE case_id = %s AND (
                entity_id::text = %s OR rfc = %s
                OR raw_payload->>'external_entity_id' = %s
            )
            LIMIT 1
            """,
            (case_id, entity_ref, entity_ref, entity_ref),
        )
        row = cur.fetchone()
        return row["entity_id"] if row else None

    def _resolve_record_uuid(self, cur: Any, case_id: uuid.UUID | str, source_id: str) -> uuid.UUID:
        cur.execute(
            """
            SELECT bank_transaction_id AS id FROM truelock.bank_transactions
            WHERE case_id = %s AND (bank_transaction_id::text = %s OR external_transaction_id = %s)
            UNION ALL
            SELECT invoice_id FROM truelock.invoices
            WHERE case_id = %s AND (invoice_id::text = %s OR uuid = %s)
            UNION ALL
            SELECT payment_id FROM truelock.payment_complements
            WHERE case_id = %s AND (payment_id::text = %s OR external_payment_id = %s)
            LIMIT 1
            """,
            (case_id, source_id, source_id, case_id, source_id, source_id, case_id, source_id, source_id),
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        return deterministic_uuid(f"record:{case_id}:{source_id}")


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
        if not row:
            row = self.db.fetch_one(
                """
                SELECT e.rfc, e.canonical_name AS name, NULL AS address,
                       v.status AS sat_status, v.snapshot_date
                FROM truelock.entities e
                LEFT JOIN truelock.v_latest_sat_69b v ON v.case_id = e.case_id AND v.rfc = e.rfc
                WHERE upper(e.rfc) = upper(%s) LIMIT 1
                """,
                (rfc,),
            )
        return _provider(row) if row else None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Provider]:
        _page(limit, offset)
        rows = self.db.fetch_all(
            """
            SELECT DISTINCT ON (upper(rfc)) rfc, legal_name AS name, address_raw AS address,
                   NULL::text AS sat_status, NULL::date AS snapshot_date
            FROM truelock.suppliers
            WHERE rfc IS NOT NULL
            ORDER BY upper(rfc), imported_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        if rows:
            return [_provider(row) for row in rows]
        return [_provider(row) for row in self.db.fetch_all(
            """
            SELECT e.rfc, e.canonical_name AS name, NULL AS address,
                   v.status AS sat_status, v.snapshot_date
            FROM truelock.entities e
            LEFT JOIN truelock.v_latest_sat_69b v ON v.case_id = e.case_id AND v.rfc = e.rfc
            WHERE e.rfc IS NOT NULL AND e.entity_type IN ('SUPPLIER', 'COMPANY', 'UNKNOWN')
            ORDER BY e.rfc LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )]

    def list_by_efos_status(self, status: str) -> list[Provider]:
        wanted = str(getattr(status, "value", status))
        return [provider for provider in self.list() if provider.efos_status.value == wanted]


class _EntityRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, entity_id: str) -> Entity | None:
        row = self.db.fetch_one(
            """
            SELECT entity_id, canonical_name, entity_type, rfc, raw_payload
            FROM truelock.entities
            WHERE entity_id::text = %s OR raw_payload->>'external_entity_id' = %s
            LIMIT 1
            """,
            (entity_id, entity_id),
        )
        return _entity(row) if row else None

    def get_by_rfc(self, rfc: str) -> Entity | None:
        row = self.db.fetch_one(
            """
            SELECT entity_id, canonical_name, entity_type, rfc, raw_payload
            FROM truelock.entities
            WHERE upper(rfc) = upper(%s) ORDER BY created_at LIMIT 1
            """,
            (rfc,),
        )
        return _entity(row) if row else None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Entity]:
        _page(limit, offset)
        return [_entity(row) for row in self.db.fetch_all(
            """
            SELECT entity_id, canonical_name, entity_type, rfc, raw_payload
            FROM truelock.entities ORDER BY entity_id LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )]


class _AccountRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, account_no: str) -> Account | None:
        row = self.db.fetch_one(
            """
            SELECT ba.account_number, ba.masked_account, ba.bank_name,
                   coalesce(e.raw_payload->>'external_entity_id', eba.entity_id::text) AS entity_id
            FROM truelock.bank_accounts ba
            JOIN truelock.entity_bank_accounts eba ON eba.bank_account_id = ba.bank_account_id
            JOIN truelock.entities e ON e.entity_id = eba.entity_id
            WHERE ba.account_number = %s OR ba.masked_account = %s LIMIT 1
            """,
            (account_no, account_no),
        )
        return _account(row) if row else None

    def list_for_entity(self, entity_id: str) -> list[Account]:
        rows = self.db.fetch_all(
            """
            SELECT ba.account_number, ba.masked_account, ba.bank_name,
                   coalesce(e.raw_payload->>'external_entity_id', eba.entity_id::text) AS entity_id
            FROM truelock.entity_bank_accounts eba
            JOIN truelock.bank_accounts ba ON ba.bank_account_id = eba.bank_account_id
            JOIN truelock.entities e ON e.entity_id = eba.entity_id
            WHERE eba.entity_id::text = %s OR e.raw_payload->>'external_entity_id' = %s
            ORDER BY ba.account_number
            """,
            (entity_id, entity_id),
        )
        return [_account(row) for row in rows]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Account]:
        _page(limit, offset)
        rows = self.db.fetch_all(
            """
            SELECT ba.account_number, ba.masked_account, ba.bank_name,
                   coalesce(e.raw_payload->>'external_entity_id', eba.entity_id::text) AS entity_id
            FROM truelock.entity_bank_accounts eba
            JOIN truelock.bank_accounts ba ON ba.bank_account_id = eba.bank_account_id
            JOIN truelock.entities e ON e.entity_id = eba.entity_id
            ORDER BY ba.account_number LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return [_account(row) for row in rows]


class _InvoiceRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, uuid_value: str) -> Invoice | None:
        row = self.db.fetch_one(
            "SELECT * FROM truelock.invoices WHERE uuid = %s ORDER BY imported_at LIMIT 1",
            (uuid_value,),
        )
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
            "SELECT * FROM truelock.invoices ORDER BY issue_timestamp, invoice_id LIMIT %s OFFSET %s",
            (limit, offset),
        )]


class _PaymentRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, payment_id: str) -> Payment | None:
        row = self.db.fetch_one(
            _payment_query(
                "pc.payment_id::text = %s OR pc.external_payment_id = %s OR pc.operation_number = %s"
            ),
            (payment_id, payment_id, payment_id),
        )
        return _payment(row) if row else None

    def list_for_invoice(self, invoice_uuid: str) -> list[Payment]:
        return [_payment(row) for row in self.db.fetch_all(
            _payment_query("pd.related_document_uuid = %s"),
            (invoice_uuid,),
        )]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Payment]:
        _page(limit, offset)
        return [_payment(row) for row in self.db.fetch_all(
            _payment_query("TRUE") + " LIMIT %s OFFSET %s",
            (limit, offset),
        )]


class _TransactionRepository:
    def __init__(self, db: PostgresRepositories) -> None:
        self.db = db

    def get(self, transaction_id: str) -> Transaction | None:
        row = self.db.fetch_one(
            _transaction_query(
                "bt.bank_transaction_id::text = %s OR bt.external_transaction_id = %s"
            ),
            (transaction_id, transaction_id),
        )
        return _transaction(row) if row else None

    def list_outgoing(self, account_no: str) -> list[Transaction]:
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query("origin.account_number = %s"),
            (account_no,),
        )]

    def list_incoming(self, account_no: str) -> list[Transaction]:
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query("destination.account_number = %s"),
            (account_no,),
        )]

    def list_for_payment(self, payment_id: str) -> list[Transaction]:
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query(
                "bt.related_payment_external_id = %s OR pc.external_payment_id = %s OR pc.payment_id::text = %s"
            ),
            (payment_id, payment_id, payment_id),
        )]

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Transaction]:
        _page(limit, offset)
        return [_transaction(row) for row in self.db.fetch_all(
            _transaction_query("TRUE") + " LIMIT %s OFFSET %s",
            (limit, offset),
        )]


def _transaction_query(where: str) -> str:
    return f"""
        SELECT coalesce(bt.external_transaction_id, bt.bank_transaction_id::text) AS transaction_id,
               bt.bank_transaction_id,
               origin.account_number AS from_account,
               destination.account_number AS to_account,
               bt.booked_at::date AS transaction_date,
               bt.amount,
               bt.related_payment_external_id AS related_payment_id,
               bt.booked_at
        FROM truelock.bank_transactions bt
        JOIN truelock.bank_accounts origin ON origin.bank_account_id = bt.origin_bank_account_id
        JOIN truelock.bank_accounts destination ON destination.bank_account_id = bt.destination_bank_account_id
        LEFT JOIN truelock.payment_complements pc
          ON pc.case_id = bt.case_id
         AND (
              pc.external_payment_id = bt.related_payment_external_id
              OR pc.payment_id::text = bt.related_payment_external_id
         )
        WHERE {where}
        ORDER BY bt.booked_at, bt.bank_transaction_id
    """


def _payment_query(where: str) -> str:
    return f"""
        SELECT coalesce(pc.external_payment_id, pc.operation_number, pc.payment_id::text) AS payment_key,
               pc.payment_id,
               pd.related_document_uuid, pc.payment_date, pc.payment_amount,
               pc.payment_form, pc.currency, pd.previous_balance, pd.remaining_balance,
               coalesce(
                 (
                   SELECT array_agg(coalesce(bt.external_transaction_id, bt.bank_transaction_id::text)
                                   ORDER BY bt.booked_at)
                   FROM truelock.bank_transactions bt
                   WHERE bt.case_id = pc.case_id
                     AND bt.related_payment_external_id = coalesce(pc.external_payment_id, pc.payment_id::text)
                 ),
                 ARRAY[]::text[]
               ) AS transaction_ids
        FROM truelock.payment_complements pc
        JOIN truelock.payment_documents pd ON pd.payment_id = pc.payment_id
        WHERE {where}
        ORDER BY pc.payment_date, pc.payment_id
    """


def _page(limit: int, offset: int) -> None:
    if limit < 0 or offset < 0:
        raise ValueError("limit and offset must not be negative")


def _number(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def _entity(row: dict[str, Any]) -> Entity:
    payload = row.get("raw_payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    external = payload.get("external_entity_id") if isinstance(payload, dict) else None
    return Entity(
        id=str(external or row["entity_id"]),
        name=row["canonical_name"],
        entity_type="individual" if row["entity_type"] == "PERSON" else "company",
        rfc=row["rfc"],
    )


def _provider(row: dict[str, Any]) -> Provider:
    statuses = {
        "PRESUNTO": "PRESUMED",
        "DEFINITIVO": "DEFINITIVE",
        "DESVIRTUADO": "INVALIDATED",
        "SENTENCIA_FAVORABLE": "FAVORABLE_JUDGMENT",
    }
    return Provider(
        rfc=row["rfc"],
        name=row["name"],
        address=row.get("address"),
        efos_status=EfosStatus(statuses.get(row.get("sat_status"), "UNKNOWN")),
        efos_listed_date=row.get("snapshot_date") if row.get("sat_status") else None,
    )


def _account(row: dict[str, Any]) -> Account:
    return Account(
        account_no=row["account_number"] or row["masked_account"],
        entity_id=str(row["entity_id"]),
        bank=row["bank_name"],
    )


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
    tx_ids = row.get("transaction_ids") or ()
    if isinstance(tx_ids, list):
        tx_ids = tuple(tx_ids)
    return Payment(
        id=str(row.get("payment_key") or row["payment_id"]),
        related_invoice_uuid=row["related_document_uuid"],
        payment_date=row["payment_date"].date() if hasattr(row["payment_date"], "date") else row["payment_date"],
        amount=_number(row["payment_amount"]),
        payment_form=row["payment_form"],
        currency=row["currency"],
        previous_balance=_number(row["previous_balance"]) if row["previous_balance"] is not None else None,
        remaining_balance=_number(row["remaining_balance"]) if row["remaining_balance"] is not None else None,
        transaction_ids=tuple(tx_ids),
    )


def _transaction(row: dict[str, Any]) -> Transaction:
    booked = row.get("booked_at")
    return Transaction(
        id=str(row.get("transaction_id") or row["bank_transaction_id"]),
        from_account=row["from_account"],
        to_account=row["to_account"],
        transaction_date=row["transaction_date"],
        amount=_number(row["amount"]),
        related_payment_id=row.get("related_payment_id"),
        booked_at=booked,
    )


def _row_json(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            _number(value)
            if isinstance(value, Decimal)
            else str(value)
            if key.endswith("_id") and value is not None
            else value
        )
        for key, value in row.items()
    }


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


def _lead_model(row: dict[str, Any]) -> Lead:
    detector_codes = list(row.get("detector_codes") or [])
    external = row.get("external_lead_key") or row.get("display_id") or str(row["lead_id"])
    entity_id = str(row["entity_id"]) if row.get("entity_id") else ""
    if not entity_id:
        entity_id = _entity_hint_from_lead_key(str(external))
    return Lead(
        lead_id=str(external),
        entity_id=entity_id,
        detector_id=detector_codes[0] if detector_codes else _detector_hint_from_lead_key(str(external)),
        reason=row["reason_summary"],
        risk_score=min(_number(row["risk_score"]) / 100.0, 1.0),
        signals=detector_codes or ([_detector_hint_from_lead_key(str(external))] if external else []),
        status=_lead_status_from_db(row.get("status")),
    )


def _entity_hint_from_lead_key(lead_key: str) -> str:
    for prefix in (
        "LEAD-PASSTHROUGH-",
        "LEAD-FAN-OUT-",
        "LEAD-FAN-IN-",
        "LEAD-SUPPLIER-CONCENTRATION-",
    ):
        if lead_key.startswith(prefix):
            return lead_key[len(prefix) :]
    return ""


def _detector_hint_from_lead_key(lead_key: str) -> str:
    if "CYCLE" in lead_key:
        return "CYCLE"
    if "PASSTHROUGH" in lead_key or "PASS_THROUGH" in lead_key:
        return "RAPID_PASS_THROUGH"
    if "SHARED_ADDRESS" in lead_key or "CONTROL" in lead_key:
        return "SHARED_ADDRESS_CONTROL"
    if "FAN-OUT" in lead_key:
        return "FAN_OUT"
    if "FAN-IN" in lead_key:
        return "FAN_IN"
    return "PERSISTED_LEAD"


def _lead_status_from_db(value: Any) -> LeadStatus:
    text = str(getattr(value, "value", value) or "OPEN")
    if text in {"SUPPORTED", "CLOSED", "INVESTIGATING"}:
        return LeadStatus.FOLLOWED
    if text in {"REJECTED", "INSUFFICIENT_EVIDENCE"}:
        return LeadStatus.DISCARDED
    return LeadStatus.OPEN


def _lead_status_to_db(status: LeadStatus | str) -> str:
    value = str(getattr(status, "value", status))
    if value == LeadStatus.FOLLOWED.value:
        return "INVESTIGATING"
    if value == LeadStatus.DISCARDED.value:
        return "REJECTED"
    return "OPEN"


def _priority_for_score(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.6:
        return "HIGH"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _case_status_to_thread(status: str) -> str:
    if status == "SUBSTANTIATED":
        return "SUPPORTED"
    if status == "INSUFFICIENT_EVIDENCE":
        return "INSUFFICIENT_EVIDENCE"
    return "REJECTED"


def _evidence_type_to_db(value: Any) -> str:
    text = str(getattr(value, "value", value))
    mapping = {
        "TRANSACTION": "BANK_TRANSACTION",
        "INVOICE": "INVOICE",
        "REGULATORY_STATUS": "SAT_69B_RECORD",
        "RELATIONSHIP": "ENTITY_RELATIONSHIP",
        "DOCUMENT": "OTHER",
    }
    return mapping.get(text, "OTHER")


def _step_dict(row: dict[str, Any]) -> dict[str, Any]:
    input_ids = row.get("input_evidence_ids") or []
    result_ids = row.get("result_evidence_ids") or []
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
        "evidence_ids": [str(value) for value in list(input_ids) + list(result_ids)],
    }
