"""Ingestion normalizers (`scripts/ingest/`, TASK-001).

The property under test throughout: **a malformed record is rejected and
reported, never repaired.** Each test names the specific wrong answer the
rejection prevents, because "it raised" is not the point — the point is
that no downstream module ever sees an invented value.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.ingest import (
    BankCsvMapping,
    IngestError,
    parse_bank_csv,
    parse_cfdi_directory,
    parse_cfdi_file,
)

CFDI = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  Version="4.0" Fecha="2026-01-15T10:30:00" Total="1160.00" SubTotal="1000.00"
  Moneda="MXN" MetodoPago="PUE" FormaPago="03" TipoDeComprobante="I">
  <cfdi:Emisor Rfc="ABC010101AAA" Nombre="Acme SA"/>
  <cfdi:Receptor Rfc="XYZ020202BBB" Nombre="Buyer SA"/>
  <cfdi:Conceptos>
    <cfdi:Concepto Descripcion="Consulting services"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="160.00"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
      UUID="123e4567-e89b-12d3-a456-426614174000"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
"""

CSV_HEADER = "transaction_id,from_account,to_account,date,amount,payment_id\n"


@pytest.fixture
def cfdi_file(tmp_path: Path) -> Path:
    path = tmp_path / "invoice.xml"
    path.write_text(CFDI, encoding="utf-8")
    return path


class TestCfdiParsing:
    def test_a_well_formed_cfdi_becomes_an_invoice(self, cfdi_file):
        result = parse_cfdi_file(cfdi_file)
        assert result.ok, result.render()
        invoice = result.records[0]
        assert invoice.uuid == "123e4567-e89b-12d3-a456-426614174000"
        assert invoice.provider_rfc == "ABC010101AAA"
        assert invoice.receiver_rfc == "XYZ020202BBB"
        assert invoice.amount == 1160.0
        assert invoice.taxes == 160.0
        assert invoice.concept == "Consulting services"

    def test_the_cfdi_datetime_becomes_a_date(self, cfdi_file):
        """Fecha carries a time; the canonical contract is a date."""
        invoice = parse_cfdi_file(cfdi_file).records[0]
        assert invoice.issue_date == date(2026, 1, 15)

    def test_a_cfdi_without_a_uuid_is_rejected(self, tmp_path):
        """No folio means no join key — silently unlinkable, not merely incomplete."""
        path = tmp_path / "no-uuid.xml"
        path.write_text(CFDI.replace('UUID="123e4567-e89b-12d3-a456-426614174000"', ""))
        result = parse_cfdi_file(path)
        assert not result.ok
        assert "uuid" in result.rejections[0].reason.lower()

    def test_a_cfdi_missing_the_emisor_is_rejected(self, tmp_path):
        path = tmp_path / "no-emisor.xml"
        path.write_text(CFDI.replace('<cfdi:Emisor Rfc="ABC010101AAA" Nombre="Acme SA"/>', ""))
        result = parse_cfdi_file(path)
        assert not result.ok
        assert "provider_rfc" in result.rejections[0].reason

    def test_malformed_xml_is_one_rejection_not_a_crash(self, tmp_path):
        """A directory of thousands must not fail because one file is corrupt."""
        path = tmp_path / "broken.xml"
        path.write_text("<cfdi:Comprobante>truncated")
        result = parse_cfdi_file(path)
        assert not result.ok
        assert "well-formed" in result.rejections[0].reason

    def test_a_directory_keeps_going_past_a_bad_file(self, tmp_path):
        (tmp_path / "good.xml").write_text(CFDI)
        (tmp_path / "bad.xml").write_text("<nope")
        result = parse_cfdi_directory(tmp_path)
        assert (result.accepted, result.rejected) == (1, 1)

    def test_an_unreadable_directory_is_an_error_not_a_rejection(self, tmp_path):
        with pytest.raises(IngestError):
            parse_cfdi_directory(tmp_path / "missing")

    def test_a_rejection_says_where_to_look(self, tmp_path):
        path = tmp_path / "broken.xml"
        path.write_text("<nope")
        rejection = parse_cfdi_file(path).rejections[0]
        assert "broken.xml" in rejection.render()


class TestBankCsvParsing:
    def _write(self, tmp_path: Path, rows: str) -> Path:
        path = tmp_path / "bank.csv"
        path.write_text(CSV_HEADER + rows, encoding="utf-8")
        return path

    def test_a_well_formed_row_becomes_a_transaction(self, tmp_path):
        path = self._write(tmp_path, "T1,ACC1,ACC2,2026-01-15,1500.00,P1\n")
        result = parse_bank_csv(path)
        assert result.ok, result.render()
        transaction = result.records[0]
        assert transaction.id == "T1"
        assert transaction.amount == 1500.0
        assert transaction.related_payment_id == "P1"

    def test_bank_formatting_is_stripped_from_amounts(self, tmp_path):
        """Thousands separators and a currency symbol are presentation, not data."""
        path = self._write(tmp_path, 'T1,ACC1,ACC2,2026-01-15,"$1,500.00",\n')
        assert parse_bank_csv(path).records[0].amount == 1500.0

    def test_a_row_missing_an_account_is_rejected_with_its_line_number(self, tmp_path):
        path = self._write(
            tmp_path, "T1,ACC1,ACC2,2026-01-15,100,\nT2,,ACC3,2026-01-16,50,\n"
        )
        result = parse_bank_csv(path)
        assert (result.accepted, result.rejected) == (1, 1)
        # Row 1 is the header, so the second data row is line 3.
        assert result.rejections[0].locator == "3"

    def test_a_missing_column_fails_the_whole_file(self, tmp_path):
        """A mapping error, not a data error — ingesting a partial table hides it."""
        path = tmp_path / "bank.csv"
        path.write_text("transaction_id,from_account,to_account,date\nT1,A,B,2026-01-15\n")
        with pytest.raises(IngestError) as caught:
            parse_bank_csv(path)
        assert "amount" in str(caught.value)

    def test_the_error_says_which_columns_were_found(self, tmp_path):
        path = tmp_path / "bank.csv"
        path.write_text("id,src,dst,when,how_much\nT1,A,B,2026-01-15,10\n")
        with pytest.raises(IngestError) as caught:
            parse_bank_csv(path)
        assert "how_much" in str(caught.value)

    def test_a_bank_specific_mapping_is_honoured(self, tmp_path):
        path = tmp_path / "other-bank.csv"
        path.write_text(
            "ref,debit_account,credit_account,value_date,importe\n"
            "T9,ACC1,ACC2,2026-02-01,42.50\n"
        )
        mapping = BankCsvMapping(
            transaction_id="ref", from_account="debit_account",
            to_account="credit_account", transaction_date="value_date",
            amount="importe", related_payment_id=None,
        )
        result = parse_bank_csv(path, mapping=mapping)
        assert result.ok, result.render()
        assert result.records[0].amount == 42.5

    def test_an_unparseable_amount_is_rejected_not_zeroed(self, tmp_path):
        """A zeroed amount would silently shrink every total downstream."""
        path = self._write(tmp_path, "T1,ACC1,ACC2,2026-01-15,pending,\n")
        result = parse_bank_csv(path)
        assert not result.ok
        assert result.accepted == 0

    def test_an_extra_column_is_ignored_not_merged(self, tmp_path):
        """Bank exports carry extra columns; that is normal, not malformed."""
        path = tmp_path / "bank.csv"
        path.write_text(
            CSV_HEADER.rstrip("\n") + ",branch\nT1,ACC1,ACC2,2026-01-15,100,,MEX-01\n"
        )
        assert parse_bank_csv(path).ok

    def test_a_missing_file_is_an_error(self, tmp_path):
        with pytest.raises(IngestError):
            parse_bank_csv(tmp_path / "nope.csv")


class TestIngestResultReporting:
    def test_a_result_reports_both_halves(self, tmp_path):
        path = tmp_path / "bank.csv"
        path.write_text(CSV_HEADER + "T1,ACC1,ACC2,2026-01-15,100,\nT2,,B,2026-01-16,1,\n")
        rendered = parse_bank_csv(path).render()
        assert "1 accepted, 1 rejected" in rendered
        assert "REJECTED" in rendered

    def test_ok_is_false_when_anything_was_refused(self, tmp_path):
        """A caller that tolerates rejections has to look at them and say so."""
        path = tmp_path / "bank.csv"
        path.write_text(CSV_HEADER + "T2,,B,2026-01-16,1,\n")
        assert parse_bank_csv(path).ok is False
