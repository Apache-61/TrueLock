"""Unit tests for deterministic fraud detectors."""
from __future__ import annotations

from truelock.detection.detectors import DetectionEngine
from truelock.seeder.demo_scenario import load_demo_scenario


def test_detection_engine_finds_round_trip_cycle():
    repo = load_demo_scenario()
    engine = DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )
    leads = engine.detect_round_trip_cycles()
    assert len(leads) >= 1
    cycle_lead = next((l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE"), None)
    assert cycle_lead is not None
    assert cycle_lead.risk_score >= 0.90
    assert "Round-trip cycle detected" in cycle_lead.reason


def test_detection_engine_finds_rapid_pass_through():
    repo = load_demo_scenario()
    engine = DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )
    leads = engine.detect_rapid_pass_through()
    assert any(l.detector_id == "DET-RAPID-PASS-THROUGH" for l in leads)


def test_detection_engine_generates_control_lead():
    repo = load_demo_scenario()
    engine = DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )
    leads = engine.generate_control_leads()
    assert len(leads) == 1
    control = leads[0]
    assert control.detector_id == "DET-SHARED-ADDRESS-CONTROL"
    assert control.risk_score < 0.50  # Legitimate control must have low risk
