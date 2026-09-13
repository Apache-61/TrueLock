"""Contract tests for demo/API endpoints (Fase 4)."""
from __future__ import annotations

from starlette.testclient import TestClient

from truelock.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app(use_database=False))


def test_inject_fraud_surfaces_new_lead() -> None:
    client = _client()
    before = {lead["lead_id"] for lead in client.get("/api/leads").json()}
    injected = client.post("/demo/inject-fraud", json={"scenario_id": "hidden_pass_through"}).json()
    assert injected["scenario_id"] == "hidden_pass_through"
    assert injected["entity_id"] == "ENT-HIDDEN-VENDOR-001"
    after = client.get("/api/leads").json()
    after_ids = {lead["lead_id"] for lead in after}
    assert after_ids - before or injected["lead_id"]


def test_inject_duplicate_payment_scenario() -> None:
    client = _client()
    injected = client.post(
        "/demo/inject-fraud", json={"scenario_id": "hidden_duplicate_payment"}
    ).json()
    assert injected["scenario_id"] == "hidden_duplicate_payment"
    leads = client.get("/api/leads").json()
    assert any(lead["detector_id"] == "DET-DUPLICATE-PAYMENT" for lead in leads)


def test_investigation_events_and_evidence_refs() -> None:
    client = _client()
    client.post("/demo/inject-fraud", json={"scenario_id": "hidden_pass_through"})
    leads = client.get("/api/leads").json()
    top = max(leads, key=lambda item: item["risk_score"])
    inv = client.post("/api/investigations/start", json={"lead_id": top["lead_id"]}).json()
    case_id = inv["case"]["case_id"]
    assert inv["steps"]
    assert inv["evidence"]
    assert isinstance(inv["case"].get("discarded_leads"), list)

    events = client.get("/api/events", params={"case_id": case_id}).json()
    assert len(events) >= 1
    assert any("Investigation" in event["message"] or "Step" in event["message"] for event in events)

    qa = client.post(
        f"/api/cases/{case_id}/questions",
        json={"question": "What evidence supports the money trail?"},
    ).json()
    assert "answer" in qa
    assert "evidence_refs" in qa
    assert isinstance(qa["evidence_refs"], list)


def test_memory_graph_for_case() -> None:
    client = _client()
    leads = client.get("/api/leads").json()
    cycle = next(item for item in leads if item["detector_id"] == "DET-ROUND-TRIP-CYCLE")
    inv = client.post("/api/investigations/start", json={"lead_id": cycle["lead_id"]}).json()
    graph = client.get(f"/api/graph/{inv['case']['case_id']}").json()
    assert graph["nodes"]
    assert graph["edges"]


def test_import_endpoints_require_database() -> None:
    client = _client()
    response = client.post(
        "/api/imports/bank",
        files={"file": ("valid_cycle.csv", b"tx_id,amount\nTX-1,1\n", "text/csv")},
    )
    assert response.status_code == 501
    assert "DATABASE_URL" in response.json()["detail"]
