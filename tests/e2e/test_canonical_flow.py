"""E2E: dataset → detector → lead → agent → case → API (memory demo)."""
from __future__ import annotations

from starlette.testclient import TestClient

from truelock.agent.gemini_client import GeminiClient
from truelock.api.app import create_app
from truelock.services.investigation_service import InvestigationService


def test_canonical_cycle_dataset_to_api() -> None:
    """Full offline path judges care about for Hito C."""
    service = InvestigationService(gemini_client=GeminiClient(api_key=""))
    leads = service.list_leads()
    cycle = next(l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE")
    assert "TX-ROOT-001" in cycle.lead_id or cycle.signals

    result = service.start_investigation(cycle.lead_id)
    case = result["case"]
    steps = result["steps"]
    evidence = result["evidence"]

    assert case["status"] == "SUBSTANTIATED"
    assert case["amount_involved"] == 1_000_000.0
    assert any("policy_version=v1" in lim or "agent_run:" in lim for lim in case["limitations"])
    assert any(str(c).startswith("agent-policy:") for c in case["citations"])

    tool_names = [s["tool"] for s in steps]
    assert len(tool_names) == len(set(tool_names)) or tool_names.count("trace_outgoing_funds") == 1
    source_ids = {e["source_id"] for e in evidence}
    assert "TX-ROOT-001" in source_ids
    assert not any(str(s).startswith("TX-FAKE") for s in source_ids)

    client = TestClient(create_app(use_database=False))
    # Mirror the same investigation via HTTP
    http_leads = client.get("/api/leads").json()
    http_cycle = next(l for l in http_leads if l["detector_id"] == "DET-ROUND-TRIP-CYCLE")
    inv = client.post("/api/investigations/start", json={"lead_id": http_cycle["lead_id"]}).json()
    case_id = inv["case"]["case_id"]

    graph = client.get(f"/api/graph/{case_id}").json()
    assert graph["nodes"] and graph["edges"]

    qa = client.post(
        f"/api/cases/{case_id}/questions",
        json={"question": "What evidence supports the money trail?"},
    ).json()
    assert qa["evidence_refs"]
    assert "answer" in qa


def test_control_lead_does_not_accuse() -> None:
    service = InvestigationService(gemini_client=GeminiClient(api_key=""))
    control = next(l for l in service.list_leads() if l.detector_id == "DET-SHARED-ADDRESS-CONTROL")
    result = service.start_investigation(control.lead_id)
    assert result["case"]["status"] != "SUBSTANTIATED"
    decisions = {s["decision"] for s in result["steps"]}
    assert "DISCARD" in decisions or result["case"]["status"] in {
        "UNSUBSTANTIATED",
        "INSUFFICIENT_EVIDENCE",
    }
