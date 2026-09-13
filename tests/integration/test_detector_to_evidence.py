"""Integration: detector → lead → tool → evidence (in-memory)."""
from __future__ import annotations

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.tools import ToolRegistry
from truelock.detection.detectors import DetectionEngine
from truelock.seeder.demo_scenario import load_demo_scenario
from truelock.services.investigation_service import InvestigationService


def test_detector_lead_tool_evidence_chain() -> None:
    repo = load_demo_scenario()
    engine = DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )
    signals = engine.collect_signals()
    assert signals
    assert all(s.source_ids for s in signals)

    leads = engine.run_all()
    cycle = next(l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE")

    tools = ToolRegistry(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )
    traced = tools.execute(
        "trace_outgoing_funds",
        {"account_id": "012180000000000001", "max_depth": 3},
    )
    assert traced.get("source_ids")
    assert traced.get("errors") in (None, [], ())

    service = InvestigationService(repo=repo, gemini_client=GeminiClient(api_key=""))
    result = service.start_investigation(cycle.lead_id)
    evidence_sources = {e["source_id"] for e in result["evidence"]}
    assert evidence_sources & set(traced["source_ids"])
