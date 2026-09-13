"""Unit coverage for EFOS parsing and ImportReport contracts (no PostgreSQL)."""
from __future__ import annotations

from pathlib import Path

import pytest

from truelock.seeder.ingestion import IngestError, parse_bank_csv, parse_cfdi_file, parse_efos_69b_csv
from truelock.services.import_service import ImportReport, ImportRejection

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures"


class TestEfosParser:
    def test_valid_snapshot_is_accepted(self) -> None:
        result = parse_efos_69b_csv(FIXTURES / "efos" / "valid_69b.csv")
        assert result.ok
        assert result.accepted == 1
        record = result.records[0]
        assert record.rfc == "LSF200820CC3"
        assert record.status == "DEFINITIVO"

    def test_partial_invalid_rows_are_reported(self) -> None:
        result = parse_efos_69b_csv(FIXTURES / "efos" / "partial_invalid_rows.csv")
        assert result.accepted == 1
        assert result.rejected == 1
        assert "status" in result.rejections[0].reason.lower() or "unknown" in result.rejections[0].reason.lower()


class TestFixtureParsers:
    def test_valid_cfdi_fixture(self) -> None:
        result = parse_cfdi_file(FIXTURES / "cfdi" / "valid_invoice.xml")
        assert result.ok
        assert result.records[0].uuid == "11111111-2222-3333-4444-555555555555"
        assert result.records[0].amount == 1000000.0

    def test_invalid_cfdi_missing_uuid(self) -> None:
        result = parse_cfdi_file(FIXTURES / "cfdi" / "invalid_missing_uuid.xml")
        assert not result.ok
        assert result.rejected == 1

    def test_valid_bank_cycle_fixture(self) -> None:
        result = parse_bank_csv(FIXTURES / "bank" / "valid_cycle.csv")
        assert result.ok
        assert [tx.id for tx in result.records] == ["TX-ROOT-001", "TX-HOP-001", "TX-RET-001"]
        assert result.records[0].related_payment_id == "PMT-ROOT-001"

    def test_bank_missing_required_column_fails_file(self) -> None:
        with pytest.raises(IngestError, match="missing required column"):
            parse_bank_csv(FIXTURES / "bank" / "missing_required_column.csv")

    def test_bank_partial_invalid_rows(self) -> None:
        result = parse_bank_csv(FIXTURES / "bank" / "partial_invalid_rows.csv")
        assert result.accepted == 1
        assert result.rejected == 1
        assert result.records[0].id == "TX-OK-002"


class TestImportReportContract:
    def test_report_exposes_counts_and_rejections(self) -> None:
        report = ImportReport(
            source_file_id="sf-1",
            dataset_kind="BANK",
            sha256="a" * 64,
            accepted=2,
            rejected=1,
            deduplicated=0,
            rejections=[ImportRejection(locator="3", reason="bad date")],
            parser_name="bank_csv",
        )
        payload = report.to_dict()
        assert payload["accepted"] == 2
        assert payload["rejected"] == 1
        assert payload["rejections"][0]["locator"] == "3"
        assert payload["reused_prior_import"] is False
