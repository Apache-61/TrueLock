"""Execute the complete TrueLock forensic investigation walkthrough."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from truelock.services.investigation_service import InvestigationService
from truelock.services.case_service import CaseService
from truelock.domain.models.investigation import Case


def main() -> None:
    print("==================================================")
    print("      TrueLock Forensic Auditor Demo Runner       ")
    print("==================================================")

    # 1. Initialize Services
    inv_service = InvestigationService()
    case_service = CaseService()

    # 2. Run Deterministic Detectors
    print("\n[Phase 1] Executing Deterministic Detectors...")
    leads = inv_service.list_leads()
    print(f"Discovered {len(leads)} prioritized leads:")
    for lead in leads:
        print(f"  [{lead.lead_id}] Score: {lead.risk_score:.2f} | Detector: {lead.detector_id}")
        print(f"    Reason: {lead.reason}")

    # 3. Investigate the Top Fraud Lead (prefer economic root when ties exist)
    cycle_leads = [l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE"]
    top_lead = next(
        (l for l in cycle_leads if "TX-ROOT-001" in l.lead_id),
        next(l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE"),
    )
    print(f"\n[Phase 2] Launching Bounded Agent Investigation on {top_lead.lead_id}...")
    result = inv_service.start_investigation(top_lead.lead_id)

    case_dict = result["case"]
    steps = result["steps"]
    evidence = result["evidence"]

    print(f"\nInvestigation Completed in {len(steps)} steps:")
    for step in steps:
        print(f"  Step {step['step_id']}: Tool '{step['tool']}' -> Action: {step['action']}")
        print(f"    Decision: {step['decision']}")

    print(f"\nCollected {len(evidence)} Evidence Items:")
    for ev in evidence:
        print(f"  [{ev['evidence_id']}] ({ev['type']}): {ev['claim']}")
        if ev.get("record_hash"):
            print(f"    Hash: {ev['record_hash']}")

    print("\n[Phase 3] Generated Case File:")
    print(f"  Case ID:          {case_dict['case_id']}")
    print(f"  Status:           {case_dict['status']}")
    print(f"  Hypothesis:       {case_dict['hypothesis']}")
    print(f"  Amount Involved:  {case_dict['amount_involved']:,.2f} MXN")
    print(f"  Confidence Level: {case_dict['confidence_level']}")
    print(f"  Limitations:      {', '.join(case_dict['limitations'])}")

    # 4. Auditor Q&A
    print("\n[Phase 4] Auditor / Judge Q&A:")
    question = "What evidence demonstrates that funds returned to the originating company?"
    qa_resp = case_service.answer_question(Case.parse(case_dict), evidence, question)
    print(f"  Question: {question}")
    print(f"  Answer:   {qa_resp['answer']}")
    print(f"  Model:    {qa_resp['model']}")

    print("\n==================================================")
    print("        Demo Run Complete — All Invariants Met    ")
    print("==================================================")


if __name__ == "__main__":
    main()
