"""Unit tests for exposure accounting invariants and evidence collection."""
from __future__ import annotations

from truelock.evidence.exposure import EvidenceCollector, ExposureCalculator
from truelock.domain.models.investigation import EvidenceStrength, EvidenceType, Outcome


def test_exposure_calculation_prevents_edge_double_counting():
    """In scenario: 1,000,000 root -> 920,000 hop -> 740,000 return.

    Supported exposure must equal root amount (1,000,000), NOT sum of all edges (2,660,000).
    Net exposure must be root - return = 260,000.
    """
    root_amount = 1000000.0
    downstream_hops = [920000.0]
    returned_amount = 740000.0

    exp = ExposureCalculator.calculate_root_flow_exposure(
        root_flow_id="FLOW-001",
        root_amount=root_amount,
        downstream_transfers=downstream_hops,
        returned_amount=returned_amount,
    )

    assert exp.root_amount == 1000000.0
    assert exp.downstream_flow == 920000.0
    assert exp.verified_returned_amount == 740000.0
    assert exp.supported_exposure == 1000000.0
    assert exp.net_exposure == 260000.0
    assert exp.policy_applied == "ROOT_FLOW_UNDUPLICATED_WITH_RETURN_OFFSET"


def test_evidence_collector_hashing_and_finding_evaluation():
    collector = EvidenceCollector()
    ev = collector.add_record(
        evidence_id="EVD-001",
        ev_type=EvidenceType.TRANSACTION,
        source_type="BANK_RECORD",
        source_id="TX-ROOT-001",
        claim="Payment of 1000000 MXN occurred on 2026-08-02",
        strength=EvidenceStrength.DIRECT,
        raw_payload={"amount": 1000000.0, "tx_id": "TX-ROOT-001"},
    )
    assert ev.record_hash is not None
    assert len(ev.record_hash) == 64

    finding = collector.evaluate_finding("FINDING-001", "LEAD-001", "Cycle confirmed")
    assert finding.outcome == Outcome.SUPPORTED
    assert "EVD-001" in finding.evidence_ids


def test_evidence_collector_insufficient_evidence():
    collector = EvidenceCollector()
    collector.add_record(
        evidence_id="EVD-CIRCUMSTANTIAL",
        ev_type=EvidenceType.REGULATORY_STATUS,
        source_type="SAT_69B",
        source_id="RFC-TEST-001",
        claim="Vendor listed under presumptive 69-B inquiry",
        strength=EvidenceStrength.CIRCUMSTANTIAL,
        raw_payload={"status": "PRESUNTO"},
    )
    finding = collector.evaluate_finding("FINDING-002", "LEAD-002", "Tax risk inquiry")
    assert finding.outcome == Outcome.INSUFFICIENT_EVIDENCE
    assert "Circumstantial indicators present" in finding.rationale


def test_evidence_collector_rejected_no_finding():
    collector = EvidenceCollector()
    finding = collector.evaluate_finding("FINDING-003", "LEAD-003", "Shared address inquiry")
    assert finding.outcome == Outcome.REJECTED
    assert "No corroborating evidence" in finding.rationale


def test_stable_evidence_source_hash():
    collector = EvidenceCollector()
    payload = {"account": "012180000000000001", "amount": 1000000.0, "timestamp": "2026-08-01T10:00:00Z"}
    ev1 = collector.add_record("EVD-A", EvidenceType.TRANSACTION, "BANK", "TX-1", "Tx 1", EvidenceStrength.DIRECT, payload)
    
    collector2 = EvidenceCollector()
    # Different order of keys inside dict
    payload_reordered = {"timestamp": "2026-08-01T10:00:00Z", "amount": 1000000.0, "account": "012180000000000001"}
    ev2 = collector2.add_record("EVD-B", EvidenceType.TRANSACTION, "BANK", "TX-1", "Tx 1", EvidenceStrength.DIRECT, payload_reordered)

    assert ev1.record_hash == ev2.record_hash

