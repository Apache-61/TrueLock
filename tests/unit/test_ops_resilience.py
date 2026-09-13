"""Fase 7: provider router, budgets, pagination, concurrency."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from starlette.testclient import TestClient

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.provider_router import ProviderRouter
from truelock.agent.usage_ledger import UsageEntry, UsageLedger, utc_now
from truelock.api.app import create_app
from truelock.services.investigation_service import InvestigationService
from truelock.services.observability_service import ObservabilityService


def test_hard_budget_forces_offline_fallback() -> None:
    ledger = UsageLedger()
    router = ProviderRouter(ledger=ledger)
    ledger.record(
        UsageEntry(
            provider="google",
            project="gemini-project-a",
            model="m",
            request_id="1",
            timestamp=utc_now(),
            status="ok",
            estimated_cost=router.hard_budget_stop_usd,
        )
    )
    client = GeminiClient(router=router, ledger=ledger)
    resp = client.generate("x", tools=[{"name": "t"}])
    assert resp.is_fallback
    assert resp.routing_reason == "hard_budget_stop"


def test_routing_event_preserves_reason() -> None:
    obs = ObservabilityService()
    router = ProviderRouter(ledger=UsageLedger(), on_routing_event=obs.record_routing_event)
    router.mark_failure("gemini-project-a", reason="http_429")
    events = obs.list_events("OPS")
    assert any(e["event_type"] == "ROUTING_EVENT" for e in events)
    assert any("http_429" in e["message"] for e in events)


def test_api_metrics_and_pagination() -> None:
    client = TestClient(create_app(use_database=False))
    assert client.get("/ready").json()["status"] == "ready"
    metrics = client.get("/api/metrics").json()
    assert "routing" in metrics
    assert "budgets" in metrics
    page = client.get("/api/leads", params={"limit": 1, "offset": 0}).json()
    assert len(page) == 1


def test_concurrent_investigations_same_lead() -> None:
    service = InvestigationService(gemini_client=GeminiClient(api_key=""))
    lead = next(l for l in service.list_leads() if l.detector_id == "DET-ROUND-TRIP-CYCLE")

    def run() -> str:
        return service.start_investigation(lead.lead_id)["case"]["case_id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: run(), range(4)))
    assert len(set(ids)) == 1


def test_events_include_full_hashes() -> None:
    client = TestClient(create_app(use_database=False))
    leads = client.get("/api/leads").json()
    cycle = next(l for l in leads if l["detector_id"] == "DET-ROUND-TRIP-CYCLE")
    inv = client.post("/api/investigations/start", json={"lead_id": cycle["lead_id"]}).json()
    events = client.get(
        "/api/events",
        params={"case_id": inv["case"]["case_id"], "limit": 100},
    ).json()
    hashed = [e for e in events if e.get("result_hash")]
    assert hashed
    assert all(len(e["result_hash"]) == 64 for e in hashed)
