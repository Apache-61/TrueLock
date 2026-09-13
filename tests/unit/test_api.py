"""Unit tests for FastAPI endpoints."""
from __future__ import annotations

from starlette.testclient import TestClient

from truelock.api.app import create_app


def _client() -> TestClient:
    # Unit tests exercise the in-memory demo path even when CI exports DATABASE_URL.
    return TestClient(create_app(use_database=False))


def test_health_check_endpoint():
    client = _client()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "gemini" in data


def test_list_leads_endpoint():
    client = _client()
    response = client.get("/api/leads")
    assert response.status_code == 200
    leads = response.json()
    assert len(leads) >= 1
    assert any(l["detector_id"] == "DET-ROUND-TRIP-CYCLE" for l in leads)


def test_start_investigation_and_qa_flow():
    client = _client()

    # Get a lead
    leads_resp = client.get("/api/leads")
    cycle_lead = next(l for l in leads_resp.json() if l["detector_id"] == "DET-ROUND-TRIP-CYCLE")
    lead_id = cycle_lead["lead_id"]

    # Start investigation
    inv_resp = client.post("/api/investigations/start", json={"lead_id": lead_id})
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    assert "case" in inv_data
    assert "steps" in inv_data
    assert "evidence" in inv_data
    case_id = inv_data["case"]["case_id"]

    # Get investigation
    get_resp = client.get(f"/api/investigations/{case_id}")
    assert get_resp.status_code == 200

    # Ask Q&A
    qa_resp = client.post(
        f"/api/cases/{case_id}/questions",
        json={"question": "What evidence proves this transaction was circular?"},
    )
    assert qa_resp.status_code == 200
    assert "answer" in qa_resp.json()
