"""Unit + scenario tests for the Fase 5 detector library."""
from __future__ import annotations

from truelock.detection.detectors import DetectionEngine
from truelock.detection.rules import DETECTOR_REGISTRY, run_all_detectors
from truelock.detection.scoring import PURSUE_THRESHOLD, aggregate_signals
from truelock.detection.dataset import CanonicalDataset
from truelock.seeder.demo_scenario import load_demo_scenario
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


def _engine(repo) -> DetectionEngine:
    return DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )


def _dataset(repo) -> CanonicalDataset:
    return CanonicalDataset(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )


def test_registry_covers_documented_patterns() -> None:
    ids = {name for name, _ in DETECTOR_REGISTRY}
    for required in {
        "DET-ROUND-TRIP-CYCLE",
        "DET-RAPID-PASS-THROUGH",
        "DET-DUPLICATE-PAYMENT",
        "DUPLICATE_INVOICE",
        "UNUSUAL_AMOUNT",
        "SUPPLIER_CONCENTRATION",
        "INVOICE_PAYMENT_MISMATCH",
        "FAN_IN",
        "FAN_OUT",
        "SHELL_NETWORK",
        "69B_CORRELATION",
        "UNUSUAL_TIMING",
        "DET-SHARED-ADDRESS-CONTROL",
    }:
        assert required in ids


def test_detection_is_deterministic() -> None:
    repo = load_demo_scenario()
    engine = _engine(repo)
    first = [(s.signal_id, s.detector_id, s.claim) for s in engine.collect_signals()]
    second = [(s.signal_id, s.detector_id, s.claim) for s in engine.collect_signals()]
    assert first == second
    leads_a = [(l.lead_id, l.risk_score, l.detector_id) for l in engine.run_all()]
    leads_b = [(l.lead_id, l.risk_score, l.detector_id) for l in engine.run_all()]
    assert leads_a == leads_b


def test_detection_engine_finds_round_trip_cycle() -> None:
    leads = _engine(load_demo_scenario()).detect_round_trip_cycles()
    assert len(leads) >= 1
    cycle_lead = next(l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE")
    assert cycle_lead.risk_score >= 0.90
    assert "Round-trip cycle detected" in cycle_lead.reason
    # Dedup: demo 3-hop cycle is a single lead
    assert len(leads) == 1
    assert "TX-ROOT-001" in cycle_lead.lead_id


def test_cycle_dedup_across_start_points() -> None:
    leads = _engine(scenario_cycle_dedup()).detect_round_trip_cycles()
    assert len(leads) == 1


def test_detection_engine_finds_rapid_pass_through() -> None:
    leads = _engine(load_demo_scenario()).detect_rapid_pass_through()
    assert any(l.detector_id == "DET-RAPID-PASS-THROUGH" for l in leads)


def test_pass_through_respects_time_window() -> None:
    pos = aggregate_signals(run_all_detectors(_dataset(scenario_pass_through_temporal(positive=True))))
    neg = aggregate_signals(run_all_detectors(_dataset(scenario_pass_through_temporal(positive=False))))
    assert any(l.detector_id == "DET-RAPID-PASS-THROUGH" for l in pos)
    assert not any(l.detector_id == "DET-RAPID-PASS-THROUGH" for l in neg)


def test_detection_engine_generates_control_lead() -> None:
    leads = _engine(load_demo_scenario()).generate_control_leads()
    assert len(leads) == 1
    control = leads[0]
    assert control.detector_id == "DET-SHARED-ADDRESS-CONTROL"
    assert control.risk_score < 0.50


def test_efos_alone_does_not_accuse() -> None:
    leads = _engine(scenario_efos_negative_no_accusation()).run_all()
    efos = [l for l in leads if l.detector_id == "69B_CORRELATION"]
    assert efos
    assert all(l.risk_score < PURSUE_THRESHOLD for l in efos)
    assert not any(l.detector_id == "SHELL_NETWORK" for l in leads)


def test_duplicate_invoice_positive_and_negative() -> None:
    pos = _engine(scenario_duplicate_invoice(positive=True)).run_all()
    neg = _engine(scenario_duplicate_invoice(positive=False)).run_all()
    assert any(l.detector_id == "DUPLICATE_INVOICE" for l in pos)
    assert not any(l.detector_id == "DUPLICATE_INVOICE" for l in neg)


def test_unusual_amount_positive_and_negative() -> None:
    pos = _engine(scenario_unusual_amount(positive=True)).run_all()
    neg = _engine(scenario_unusual_amount(positive=False)).run_all()
    assert any(l.detector_id == "UNUSUAL_AMOUNT" for l in pos)
    assert not any(l.detector_id == "UNUSUAL_AMOUNT" for l in neg)


def test_invoice_payment_mismatch_positive_and_negative() -> None:
    pos = _engine(scenario_invoice_payment_mismatch(positive=True)).run_all()
    neg = _engine(scenario_invoice_payment_mismatch(positive=False)).run_all()
    assert any(l.detector_id == "INVOICE_PAYMENT_MISMATCH" for l in pos)
    assert not any(l.detector_id == "INVOICE_PAYMENT_MISMATCH" for l in neg)


def test_fan_in_out_positive_and_negative() -> None:
    assert any(l.detector_id == "FAN_IN" for l in _engine(scenario_fan_in(positive=True)).run_all())
    assert not any(l.detector_id == "FAN_IN" for l in _engine(scenario_fan_in(positive=False)).run_all())
    assert any(l.detector_id == "FAN_OUT" for l in _engine(scenario_fan_out(positive=True)).run_all())
    assert not any(l.detector_id == "FAN_OUT" for l in _engine(scenario_fan_out(positive=False)).run_all())


def test_concentration_shell_timing_positive_and_negative() -> None:
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


def test_signals_cite_sources() -> None:
    signals = _engine(load_demo_scenario()).collect_signals()
    assert signals
    for signal in signals:
        assert signal.source_ids, f"{signal.signal_id} missing source_ids"
        assert signal.claim
