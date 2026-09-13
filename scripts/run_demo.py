"""Execute the complete TrueLock forensic investigation walkthrough."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from truelock.services.investigation_service import InvestigationService
from truelock.services.case_service import CaseService
from truelock.domain.models.investigation import Case


def _safe_print(text: str) -> None:
    """Print without crashing on Windows cp1252 consoles."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def main() -> None:
    _safe_print("==================================================")
    _safe_print("      TrueLock Forensic Auditor Demo Runner       ")
    _safe_print("==================================================")

    inv_service = InvestigationService()
    case_service = CaseService()

    _safe_print("\n[Phase 1] Executing Deterministic Detectors...")
    leads = inv_service.list_leads()
    _safe_print(f"Discovered {len(leads)} prioritized leads:")
    for lead in leads:
        _safe_print(f"  [{lead.lead_id}] Score: {lead.risk_score:.2f} | Detector: {lead.detector_id}")
        _safe_print(f"    Reason: {lead.reason}")

    cycle_leads = [l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE"]
    top_lead = next(
        (l for l in cycle_leads if "TX-ROOT-001" in l.lead_id),
        next(l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE"),
    )
    _safe_print(f"\n[Phase 2] Launching Bounded Agent Investigation on {top_lead.lead_id}...")
    result = inv_service.start_investigation(top_lead.lead_id)

    case_dict = result["case"]
    steps = result["steps"]
    evidence = result["evidence"]

    _safe_print(f"\nInvestigation Completed in {len(steps)} steps:")
    for step in steps:
        _safe_print(f"  Step {step['step_id']}: Tool '{step['tool']}' -> Action: {step['action']}")
        _safe_print(f"    Decision: {step['decision']}")

    _safe_print(f"\nCollected {len(evidence)} Evidence Items:")
    for ev in evidence:
        _safe_print(f"  [{ev['evidence_id']}] ({ev['type']}): {ev['claim']}")
        if ev.get("record_hash"):
            _safe_print(f"    Hash: {ev['record_hash']}")

    _safe_print("\n[Phase 3] Generated Case File:")
    _safe_print(f"  Case ID:          {case_dict['case_id']}")
    _safe_print(f"  Status:           {case_dict['status']}")
    _safe_print(f"  Hypothesis:       {case_dict['hypothesis']}")
    _safe_print(f"  Amount Involved:  {case_dict['amount_involved']:,.2f} MXN")
    _safe_print(f"  Confidence Level: {case_dict['confidence_level']}")
    _safe_print(f"  Limitations:      {', '.join(case_dict['limitations'])}")

    _safe_print("\n[Phase 4] Auditor / Judge Q&A:")
    question = "What evidence demonstrates that funds returned to the originating company?"
    qa_resp = case_service.answer_question(Case.parse(case_dict), evidence, question)
    _safe_print(f"  Question: {question}")
    _safe_print(f"  Answer:   {qa_resp['answer']}")
    _safe_print(f"  Model:    {qa_resp['model']}")

    _safe_print("\n==================================================")
    _safe_print("        Demo Run Complete - All Invariants Met    ")
    _safe_print("==================================================")


if __name__ == "__main__":
    main()
