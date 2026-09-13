"""Scenario regression: answer keys match detector outputs (Fase 5)."""
from __future__ import annotations

import json
from pathlib import Path

from truelock.detection.detectors import DetectionEngine
from truelock.detection.scoring import PURSUE_THRESHOLD
from truelock.seeder.detector_scenarios import (
    scenario_cycle_dedup,
    scenario_duplicate_invoice,
    scenario_efos_negative_no_accusation,
    scenario_fan_in,
    scenario_fan_out,
    scenario_invoice_payment_mismatch,
    scenario_pass_through_temporal,
    scenario_shell_network,
    scenario_supplier_concentration,
    scenario_unusual_amount,
    scenario_unusual_timing,
)

ROOT = Path(__file__).resolve().parents[2]
ANSWER_KEYS = ROOT / "data" / "answer_keys"


def _engine(repo) -> DetectionEngine:
    return DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )


def _load(name: str) -> dict:
    return json.loads((ANSWER_KEYS / name).read_text(encoding="utf-8"))


def test_answer_key_duplicate_invoice() -> None:
    key = _load("duplicate_invoice_answer_key.json")
    pos = _engine(scenario_duplicate_invoice(positive=True)).run_all()
    neg = _engine(scenario_duplicate_invoice(positive=False)).run_all()
    assert any(l.detector_id == key["detector_id"] for l in pos)
    assert not any(l.detector_id == key["detector_id"] for l in neg)


def test_answer_key_unusual_amount() -> None:
    key = _load("unusual_amount_answer_key.json")
    pos = _engine(scenario_unusual_amount(positive=True)).run_all()
    neg = _engine(scenario_unusual_amount(positive=False)).run_all()
    assert any(l.detector_id == key["detector_id"] for l in pos)
    assert not any(l.detector_id == key["detector_id"] for l in neg)


def test_answer_key_mismatch_and_fans() -> None:
    assert any(
        l.detector_id == "INVOICE_PAYMENT_MISMATCH"
        for l in _engine(scenario_invoice_payment_mismatch(positive=True)).run_all()
    )
    assert any(l.detector_id == "FAN_IN" for l in _engine(scenario_fan_in(positive=True)).run_all())
    assert any(l.detector_id == "FAN_OUT" for l in _engine(scenario_fan_out(positive=True)).run_all())


def test_answer_key_pass_through_and_cycle_dedup() -> None:
    pos = _engine(scenario_pass_through_temporal(positive=True)).run_all()
    neg = _engine(scenario_pass_through_temporal(positive=False)).run_all()
    assert any(l.detector_id == "DET-RAPID-PASS-THROUGH" for l in pos)
    assert not any(l.detector_id == "DET-RAPID-PASS-THROUGH" for l in neg)
    cycles = _engine(scenario_cycle_dedup()).detect_round_trip_cycles()
    assert len(cycles) == _load("circular_flow_dedup_answer_key.json")["expected_leads"][0]["exact_count"]


def test_answer_key_efos_negative() -> None:
    key = _load("efos_negative_no_accusation_answer_key.json")
    leads = _engine(scenario_efos_negative_no_accusation()).run_all()
    efos = [l for l in leads if l.detector_id == "69B_CORRELATION"]
    assert efos
    assert all(l.risk_score <= key["expected_leads"][0]["max_risk_score"] for l in efos)
    assert all(l.risk_score < PURSUE_THRESHOLD for l in efos)
    for forbidden in key["forbidden_detectors"]:
        assert not any(l.detector_id == forbidden for l in leads)


def test_answer_key_concentration_shell_timing() -> None:
    assert any(
        l.detector_id == "SUPPLIER_CONCENTRATION"
        for l in _engine(scenario_supplier_concentration(positive=True)).run_all()
    )
    assert not any(
        l.detector_id == "SUPPLIER_CONCENTRATION"
        for l in _engine(scenario_supplier_concentration(positive=False)).run_all()
    )
    assert any(
        l.detector_id == "SHELL_NETWORK"
        for l in _engine(scenario_shell_network(positive=True)).run_all()
    )
    assert not any(
        l.detector_id == "SHELL_NETWORK"
        for l in _engine(scenario_shell_network(positive=False)).run_all()
    )
    assert any(
        l.detector_id == "UNUSUAL_TIMING"
        for l in _engine(scenario_unusual_timing(positive=True)).run_all()
    )
    assert not any(
        l.detector_id == "UNUSUAL_TIMING"
        for l in _engine(scenario_unusual_timing(positive=False)).run_all()
    )


def test_eval_corpus_packs_exist() -> None:
    corpus = ROOT / "data" / "eval_corpus"
    for relative in (
        "eval/round_trip_cycle_p0.json",
        "eval/shared_address_control.json",
        "eval/efos_contextual_only.json",
        "train/hidden_pass_through.json",
    ):
        pack = json.loads((corpus / relative).read_text(encoding="utf-8"))
        assert "input_lead" in pack
        assert "allowed_tools" in pack
        assert "expected_terminal_decision" in pack
        assert "audit_questions" in pack or relative.startswith("train/")
