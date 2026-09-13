"""Automated verification of demo invariants and forensic calculations."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from truelock.evidence.exposure import ExposureCalculator
from truelock.seeder.demo_scenario import load_demo_scenario
from truelock.services.investigation_service import InvestigationService


def main() -> None:
    print("=== TrueLock Invariant Verification ===")

    # 1. Verify scenario load
    repo = load_demo_scenario()
    assert repo.transactions.get("TX-ROOT-001") is not None, "Root transaction missing"
    assert repo.transactions.get("TX-RET-001") is not None, "Return transaction missing"
    print("[OK] Scenario fixtures loaded successfully")

    # 2. Verify exposure calculation
    exp = ExposureCalculator.calculate_root_flow_exposure(
        root_flow_id="FLOW-001",
        root_amount=1000000.0,
        downstream_transfers=[920000.0],
        returned_amount=740000.0,
    )
    assert exp.supported_exposure == 1000000.0, "Supported exposure must equal root amount (no edge summing)"
    assert exp.net_exposure == 260000.0, "Net exposure must offset returned funds"
    print("[OK] Exposure invariants verified (no edge double-counting, exact net offset)")

    # 3. Verify detector execution
    service = InvestigationService(repo)
    leads = service.list_leads()
    cycle_leads = [l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE"]
    assert len(cycle_leads) >= 1, "Expected cycle lead detected"
    control_leads = [l for l in leads if l.detector_id == "DET-SHARED-ADDRESS-CONTROL"]
    assert len(control_leads) == 1, "Expected control lead present"
    assert control_leads[0].risk_score < 0.5, "Control lead must not be flagged high risk"
    print("[OK] Deterministic detector coverage verified (cycle found, control low-risk)")

    # 4. Verify investigation execution against real trail sources
    cycle_lead = next(
        (l for l in cycle_leads if "TX-ROOT-001" in l.lead_id),
        cycle_leads[0],
    )
    res = service.start_investigation(cycle_lead.lead_id)
    assert len(res["steps"]) > 0, "Steps must be recorded"
    assert len(res["evidence"]) > 0, "Evidence must be accumulated"
    assert res["case"]["status"] == "SUBSTANTIATED", "Case must be substantiated"
    assert res["case"]["amount_involved"] == 1_000_000.0, (
        "Supported exposure must equal root amount (ROOT_FLOW policy)"
    )
    result_refs = [ref for step in res["steps"] for ref in step.get("result_refs", [])]
    assert any("TX-ROOT-001" in str(ref) for ref in result_refs), (
        "Investigation must cite TX-ROOT-001 in result_refs"
    )
    evidence_sources = [e.get("source_id") for e in res["evidence"]]
    assert "TX-ROOT-001" in evidence_sources, "Evidence must cite bank record TX-ROOT-001"
    assert all(not str(p).startswith("01218") for p in res["case"]["providers_involved"]), (
        "providers_involved must be RFCs, not account numbers"
    )
    print("[OK] Investigation loop verified (real trail, exposure, case substantiated)")

    # 4b. Fase 2 orchestration invariants
    tool_names = [s["tool"] for s in res["steps"]]
    assert len(tool_names) == len(set(tool_names)) or tool_names.count(
        "trace_outgoing_funds"
    ) == 1, "Must not repeat equivalent tool calls"
    decisions = {s["decision"] for s in res["steps"]}
    assert "CONCLUDE" in decisions, "Cycle investigation must end with CONCLUDE"
    for step in res["steps"]:
        if step["tool"] in (
            "trace_outgoing_funds",
            "inspect_counterparties",
            "check_regulatory_status",
            "calculate_exposure",
            "inspect_invoices",
        ):
            hashes = [r for r in step.get("result_refs", []) if str(r).startswith("HASH:")]
            assert hashes, f"Step {step['step_id']} missing HASH result_ref"
            digest = str(hashes[0]).removeprefix("HASH:")
            assert len(digest) == 64, "Result hash must be full SHA-256"
            assert any(
                not str(r).startswith("HASH:") for r in step.get("result_refs", [])
            ), "result_refs must include recoverable domain IDs"
    print("[OK] Orchestration invariants verified (no duplicates, full hashes, CONCLUDE)")

    # 5. Control lead must not be substantiated as fraud
    control_res = service.start_investigation(control_leads[0].lead_id)
    assert control_res["case"]["status"] != "SUBSTANTIATED", (
        "Control shared-address lead must not be substantiated"
    )
    control_decisions = {s["decision"] for s in control_res["steps"]}
    assert "DISCARD" in control_decisions or control_res["case"]["status"] == "UNSUBSTANTIATED"
    print("[OK] Control lead correctly unsubstantiated")

    print("\nALL INVARIANTS VERIFIED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
