"""Auditable import pipeline over CFDI, bank CSV, and EFOS parsers.

Persists accepted records into the canonical schema while preserving every
rejection and file-level provenance. Re-importing the same SHA-256 is
idempotent and returns the prior report without mutating fraud case status.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from truelock.database.repositories.postgres import PostgresRepositories, deterministic_uuid
from truelock.domain.models import Invoice, Transaction
from truelock.seeder.ingestion.bank_csv import BankCsvMapping, parse_bank_csv
from truelock.seeder.ingestion.cfdi import parse_cfdi_file
from truelock.seeder.ingestion.efos import EfosRecord, parse_efos_69b_csv
from truelock.seeder.ingestion.errors import IngestError, IngestResult, Rejection


@dataclass(frozen=True)
class ImportRejection:
    locator: str
    reason: str
    error_code: str = "VALIDATION"


@dataclass(frozen=True)
class ImportReport:
    source_file_id: str
    dataset_kind: str
    sha256: str
    accepted: int
    rejected: int
    deduplicated: int
    rejections: list[ImportRejection] = field(default_factory=list)
    reused_prior_import: bool = False
    parser_name: str = ""
    parser_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file_id": self.source_file_id,
            "dataset_kind": self.dataset_kind,
            "sha256": self.sha256,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "deduplicated": self.deduplicated,
            "reused_prior_import": self.reused_prior_import,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "rejections": [
                {"locator": item.locator, "reason": item.reason, "error_code": item.error_code}
                for item in self.rejections
            ],
        }


class ImportService:
    """Translate parser IngestResult values into auditable PostgreSQL rows."""

    PARSER_VERSION = "1.0.0"

    def __init__(self, database: PostgresRepositories, *, case_id: uuid.UUID | str | None = None) -> None:
        self.database = database
        self.case_id = case_id or database.canonical_case_id()
        if not self.case_id:
            raise ValueError("ImportService requires an existing case (CASE-DEMO-001)")

    def import_cfdi(self, path: Path | str) -> ImportReport:
        path = Path(path)
        digest = _file_sha256(path)
        prior = self._prior_report(digest, "CFDI_INVOICE", "cfdi_4_xml")
        if prior:
            return prior
        try:
            result = parse_cfdi_file(path)
        except IngestError as error:
            return self._persist_failed_file(
                path, digest, "CFDI_INVOICE", "cfdi_4_xml", str(error)
            )
        return self._persist_cfdi(path, digest, result)

    def import_bank_csv(self, path: Path | str, *, mapping: BankCsvMapping | None = None) -> ImportReport:
        path = Path(path)
        digest = _file_sha256(path)
        prior = self._prior_report(digest, "BANK", "bank_csv")
        if prior:
            return prior
        try:
            result = parse_bank_csv(path, mapping=mapping or BankCsvMapping())
        except IngestError as error:
            return self._persist_failed_file(path, digest, "BANK", "bank_csv", str(error))
        return self._persist_bank(path, digest, result)

    def import_efos_69b(
        self, path: Path | str, *, snapshot_date: date | None = None
    ) -> ImportReport:
        """Import SAT 69-B context only — never changes finding/case fraud state."""
        path = Path(path)
        digest = _file_sha256(path)
        prior = self._prior_report(digest, "SAT_69B", "efos_69b_csv")
        if prior:
            return prior
        try:
            result = parse_efos_69b_csv(path, snapshot_date=snapshot_date)
        except IngestError as error:
            return self._persist_failed_file(path, digest, "SAT_69B", "efos_69b_csv", str(error))
        return self._persist_efos(path, digest, result)

    def _prior_report(self, digest: str, dataset_kind: str, parser_name: str) -> ImportReport | None:
        existing = self.database.find_source_file_by_hash(self.case_id, digest)
        if not existing:
            return None
        rejections = [
            ImportRejection(
                locator=row["source_locator"],
                reason=row["error_message"],
                error_code=row["error_code"],
            )
            for row in self.database.list_ingest_rejections(existing["source_file_id"])
        ]
        meta = existing.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        return ImportReport(
            source_file_id=str(existing["source_file_id"]),
            dataset_kind=dataset_kind,
            sha256=digest,
            accepted=int(existing.get("record_count") or 0),
            rejected=int(existing.get("rejected_count") or 0),
            deduplicated=int(meta.get("deduplicated") or 0),
            rejections=rejections,
            reused_prior_import=True,
            parser_name=parser_name,
            parser_version=existing.get("parser_version") or self.PARSER_VERSION,
        )

    def _persist_failed_file(
        self, path: Path, digest: str, dataset_kind: str, parser_name: str, reason: str
    ) -> ImportReport:
        source_file_id = deterministic_uuid(f"source:{self.case_id}:{digest}")
        with self.database.connection() as conn, conn.cursor() as cur:
            self._insert_source_file(
                cur,
                source_file_id=source_file_id,
                path=path,
                digest=digest,
                dataset_kind=dataset_kind,
                parser_name=parser_name,
                status="REJECTED",
                record_count=0,
                rejected_count=1,
                metadata={"deduplicated": 0},
            )
            cur.execute(
                """
                INSERT INTO truelock.ingest_rejections (
                    source_file_id, source_locator, error_code, error_message
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (source_file_id, "file", "INGEST_ERROR", reason),
            )
        return ImportReport(
            source_file_id=str(source_file_id),
            dataset_kind=dataset_kind,
            sha256=digest,
            accepted=0,
            rejected=1,
            deduplicated=0,
            rejections=[ImportRejection(locator="file", reason=reason, error_code="INGEST_ERROR")],
            parser_name=parser_name,
            parser_version=self.PARSER_VERSION,
        )

    def _persist_cfdi(self, path: Path, digest: str, result: IngestResult) -> ImportReport:
        source_file_id = deterministic_uuid(f"source:{self.case_id}:{digest}")
        deduped = 0
        with self.database.connection() as conn, conn.cursor() as cur:
            status = "IMPORTED" if result.ok else ("PARTIAL" if result.records else "REJECTED")
            self._insert_source_file(
                cur,
                source_file_id=source_file_id,
                path=path,
                digest=digest,
                dataset_kind="CFDI_INVOICE",
                parser_name="cfdi_4_xml",
                status=status,
                record_count=len(result.records),
                rejected_count=len(result.rejections),
                metadata={"deduplicated": 0},
            )
            for invoice in result.records:
                assert isinstance(invoice, Invoice)
                invoice_id = deterministic_uuid(f"invoice:{self.case_id}:{invoice.uuid}")
                cur.execute(
                    "SELECT 1 FROM truelock.invoices WHERE case_id = %s AND uuid = %s",
                    (self.case_id, invoice.uuid),
                )
                if cur.fetchone():
                    deduped += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO truelock.invoices (
                        invoice_id, case_id, source_file_id, source_locator, record_sha256,
                        uuid, version, issue_timestamp, rfc_issuer, rfc_receiver,
                        subtotal, tax_total, total, currency, amount_mxn, cfdi_type,
                        payment_method, payment_form, cfdi_status, raw_payload
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        invoice_id,
                        self.case_id,
                        source_file_id,
                        f"uuid:{invoice.uuid}",
                        hashlib.sha256(invoice.uuid.encode()).hexdigest(),
                        invoice.uuid,
                        invoice.version,
                        datetime.combine(invoice.issue_date, datetime.min.time(), tzinfo=timezone.utc),
                        invoice.provider_rfc,
                        invoice.receiver_rfc,
                        invoice.subtotal or invoice.amount,
                        invoice.taxes or 0,
                        invoice.amount,
                        invoice.currency,
                        invoice.amount,
                        invoice.cfdi_type or "I",
                        invoice.payment_method,
                        invoice.payment_form,
                        json.dumps(invoice.to_dict()),
                    ),
                )
            self._insert_rejections(cur, source_file_id, result.rejections)
            if deduped:
                cur.execute(
                    "UPDATE truelock.source_files SET metadata = metadata || %s::jsonb WHERE source_file_id = %s",
                    (json.dumps({"deduplicated": deduped}), source_file_id),
                )
        return ImportReport(
            source_file_id=str(source_file_id),
            dataset_kind="CFDI_INVOICE",
            sha256=digest,
            accepted=len(result.records),
            rejected=len(result.rejections),
            deduplicated=deduped,
            rejections=[ImportRejection(r.locator, r.reason) for r in result.rejections],
            parser_name="cfdi_4_xml",
            parser_version=self.PARSER_VERSION,
        )

    def _persist_bank(self, path: Path, digest: str, result: IngestResult) -> ImportReport:
        source_file_id = deterministic_uuid(f"source:{self.case_id}:{digest}")
        deduped = 0
        with self.database.connection() as conn, conn.cursor() as cur:
            status = "IMPORTED" if result.ok else ("PARTIAL" if result.records else "REJECTED")
            self._insert_source_file(
                cur,
                source_file_id=source_file_id,
                path=path,
                digest=digest,
                dataset_kind="BANK",
                parser_name="bank_csv",
                status=status,
                record_count=len(result.records),
                rejected_count=len(result.rejections),
                metadata={"deduplicated": 0},
            )
            for tx in result.records:
                assert isinstance(tx, Transaction)
                cur.execute(
                    """
                    SELECT 1 FROM truelock.bank_transactions
                    WHERE case_id = %s AND external_transaction_id = %s
                    """,
                    (self.case_id, tx.id),
                )
                if cur.fetchone():
                    deduped += 1
                    continue
                origin_id = self._ensure_account(cur, source_file_id, tx.from_account)
                dest_id = self._ensure_account(cur, source_file_id, tx.to_account)
                tx_id = deterministic_uuid(f"tx:{self.case_id}:{tx.id}")
                cur.execute(
                    """
                    INSERT INTO truelock.bank_transactions (
                        bank_transaction_id, case_id, source_file_id, source_locator,
                        external_transaction_id, related_payment_external_id,
                        observed_bank_account_id, booked_at, value_date, direction,
                        origin_bank_account_id, destination_bank_account_id,
                        amount, currency, amount_mxn, record_sha256, raw_payload
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'DEBIT',
                        %s, %s, %s, 'MXN', %s, %s, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        tx_id,
                        self.case_id,
                        source_file_id,
                        f"tx:{tx.id}",
                        tx.id,
                        tx.related_payment_id,
                        origin_id,
                        datetime.combine(tx.transaction_date, datetime.min.time(), tzinfo=timezone.utc),
                        tx.transaction_date,
                        origin_id,
                        dest_id,
                        tx.amount,
                        tx.amount,
                        hashlib.sha256(tx.id.encode()).hexdigest(),
                        json.dumps(tx.to_dict()),
                    ),
                )
            self._insert_rejections(cur, source_file_id, result.rejections)
            if deduped:
                cur.execute(
                    "UPDATE truelock.source_files SET metadata = metadata || %s::jsonb WHERE source_file_id = %s",
                    (json.dumps({"deduplicated": deduped}), source_file_id),
                )
        return ImportReport(
            source_file_id=str(source_file_id),
            dataset_kind="BANK",
            sha256=digest,
            accepted=len(result.records),
            rejected=len(result.rejections),
            deduplicated=deduped,
            rejections=[ImportRejection(r.locator, r.reason) for r in result.rejections],
            parser_name="bank_csv",
            parser_version=self.PARSER_VERSION,
        )

    def _persist_efos(self, path: Path, digest: str, result: IngestResult) -> ImportReport:
        source_file_id = deterministic_uuid(f"source:{self.case_id}:{digest}")
        deduped = 0
        with self.database.connection() as conn, conn.cursor() as cur:
            status = "IMPORTED" if result.ok else ("PARTIAL" if result.records else "REJECTED")
            self._insert_source_file(
                cur,
                source_file_id=source_file_id,
                path=path,
                digest=digest,
                dataset_kind="SAT_69B",
                parser_name="efos_69b_csv",
                status=status,
                record_count=len(result.records),
                rejected_count=len(result.rejections),
                metadata={"deduplicated": 0, "contextual_only": True},
            )
            snapshot_dates = {
                record.snapshot_date for record in result.records if isinstance(record, EfosRecord)
            }
            for snap_date in snapshot_dates or {date.today()}:
                snapshot_id = deterministic_uuid(f"efos-snap:{self.case_id}:{digest}:{snap_date.isoformat()}")
                cur.execute(
                    """
                    INSERT INTO truelock.sat_69b_snapshots (
                        sat_snapshot_id, source_file_id, snapshot_date, publication_reference, notes
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        snapshot_id,
                        source_file_id,
                        snap_date,
                        "import-service",
                        "Contextual SAT 69-B import; does not change case fraud status",
                    ),
                )
                for record in result.records:
                    assert isinstance(record, EfosRecord)
                    if record.snapshot_date != snap_date:
                        continue
                    cur.execute(
                        """
                        SELECT 1
                        FROM truelock.sat_69b_records sr
                        JOIN truelock.sat_69b_snapshots ss ON ss.sat_snapshot_id = sr.sat_snapshot_id
                        WHERE ss.source_file_id = %s AND sr.rfc = %s AND ss.snapshot_date = %s
                        """,
                        (source_file_id, record.rfc, snap_date),
                    )
                    if cur.fetchone():
                        deduped += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO truelock.sat_69b_records (
                            sat_record_id, sat_snapshot_id, rfc, legal_name, status,
                            source_publication_date, source_locator, raw_status_text, raw_row_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            deterministic_uuid(f"efos:{self.case_id}:{digest}:{record.rfc}:{snap_date}"),
                            snapshot_id,
                            record.rfc,
                            record.legal_name,
                            record.status,
                            snap_date,
                            record.source_locator,
                            record.raw_status_text,
                            json.dumps(
                                {
                                    "rfc": record.rfc,
                                    "status": record.status,
                                    "contextual_only": True,
                                }
                            ),
                        ),
                    )
            self._insert_rejections(cur, source_file_id, result.rejections)
            if deduped:
                cur.execute(
                    "UPDATE truelock.source_files SET metadata = metadata || %s::jsonb WHERE source_file_id = %s",
                    (json.dumps({"deduplicated": deduped}), source_file_id),
                )
        return ImportReport(
            source_file_id=str(source_file_id),
            dataset_kind="SAT_69B",
            sha256=digest,
            accepted=len(result.records),
            rejected=len(result.rejections),
            deduplicated=deduped,
            rejections=[ImportRejection(r.locator, r.reason) for r in result.rejections],
            parser_name="efos_69b_csv",
            parser_version=self.PARSER_VERSION,
        )

    def _insert_source_file(
        self,
        cur: Any,
        *,
        source_file_id: uuid.UUID,
        path: Path,
        digest: str,
        dataset_kind: str,
        parser_name: str,
        status: str,
        record_count: int,
        rejected_count: int,
        metadata: dict[str, Any],
    ) -> None:
        cur.execute(
            """
            INSERT INTO truelock.source_files (
                source_file_id, case_id, original_filename, dataset_kind, media_type,
                byte_size, sha256, parser_name, parser_version, status,
                record_count, rejected_count, ingested_at, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, clock_timestamp(), %s::jsonb
            )
            ON CONFLICT (case_id, sha256) DO NOTHING
            """,
            (
                source_file_id,
                self.case_id,
                path.name,
                dataset_kind,
                "text/csv" if path.suffix.lower() == ".csv" else "application/xml",
                path.stat().st_size if path.exists() else 0,
                digest,
                parser_name,
                self.PARSER_VERSION,
                status,
                record_count,
                rejected_count,
                json.dumps(metadata),
            ),
        )
        cur.execute(
            """
            INSERT INTO truelock.case_source_files (case_id, source_file_id)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
            """,
            (self.case_id, source_file_id),
        )

    def _insert_rejections(self, cur: Any, source_file_id: uuid.UUID, rejections: list[Rejection]) -> None:
        for rejection in rejections:
            cur.execute(
                """
                INSERT INTO truelock.ingest_rejections (
                    source_file_id, source_locator, error_code, error_message
                ) VALUES (%s, %s, %s, %s)
                """,
                (source_file_id, rejection.locator, "VALIDATION", rejection.reason),
            )

    def _ensure_account(self, cur: Any, source_file_id: uuid.UUID, account_no: str) -> uuid.UUID:
        cur.execute(
            """
            SELECT bank_account_id FROM truelock.bank_accounts
            WHERE case_id = %s AND account_number = %s
            """,
            (self.case_id, account_no),
        )
        row = cur.fetchone()
        if row:
            account_id = row["bank_account_id"]
        else:
            account_id = deterministic_uuid(f"account:{self.case_id}:{account_no}")
            fingerprint = hashlib.sha256(account_no.encode("utf-8")).hexdigest()
            masked = ("*" * max(len(account_no) - 4, 0)) + account_no[-4:]
            cur.execute(
                """
                INSERT INTO truelock.bank_accounts (
                    bank_account_id, case_id, account_fingerprint, account_number,
                    masked_account, bank_name, currency, source_file_id
                ) VALUES (%s, %s, %s, %s, %s, %s, 'MXN', %s)
                ON CONFLICT DO NOTHING
                """,
                (account_id, self.case_id, fingerprint, account_no, masked, "Imported", source_file_id),
            )

        # Stub entity so detectors/investigator can resolve account → party.
        entity_id = deterministic_uuid(f"entity:{self.case_id}:acct:{account_no}")
        cur.execute(
            """
            INSERT INTO truelock.entities (
                entity_id, case_id, entity_type, canonical_name, legal_name, rfc,
                source_file_id, source_locator, raw_payload
            ) VALUES (
                %s, %s, 'BANK_ACCOUNT', %s, %s, NULL, %s, %s, %s::jsonb
            )
            ON CONFLICT DO NOTHING
            """,
            (
                entity_id,
                self.case_id,
                f"Imported account {account_no[-4:]}",
                f"Imported account {account_no[-4:]}",
                source_file_id,
                f"account:{account_no}",
                json.dumps({"external_entity_id": account_no, "account_number": account_no}),
            ),
        )
        cur.execute(
            """
            INSERT INTO truelock.entity_bank_accounts (
                entity_id, bank_account_id, is_primary, source_file_id, source_locator
            ) VALUES (%s, %s, true, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (entity_id, account_id, source_file_id, f"account:{account_no}"),
        )
        return account_id


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
