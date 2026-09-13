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

    # 4. Verify investigation execution
    res = service.start_investigation(cycle_leads[0].lead_id)
    assert len(res["steps"]) > 0, "Steps must be recorded"
    assert len(res["evidence"]) > 0, "Evidence must be accumulated"
    assert res["case"]["status"] == "SUBSTANTIATED", "Case must be substantiated"
    print("[OK] Investigation loop verified (steps recorded, evidence collected, case substantiated)")

    print("\nALL INVARIANTS VERIFIED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
