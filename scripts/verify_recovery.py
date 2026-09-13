#!/usr/bin/env python3
"""Verify Fase 7 recovery / resilience invariants (executable runbook)."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from starlette.testclient import TestClient

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.provider_router import ProviderRouter
from truelock.agent.usage_ledger import UsageEntry, UsageLedger, utc_now
from truelock.api.app import create_app
from truelock.services.investigation_service import InvestigationService
from truelock.services.observability_service import ObservabilityService


def main() -> int:
    print("=== TrueLock Recovery Verification (Fase 7) ===")
    failures: list[str] = []

    # 1. Offline fallback when no keys
    client = GeminiClient(api_key="")
    assert not client.is_configured
    offline = client.generate("ping", tools=[{"name": "trace_outgoing_funds"}])
    assert offline.is_fallback and offline.function_call is None
    print("[OK] Provider outage falls back offline without inventing tool calls")

    # 2. Budget hard stop
    ledger = UsageLedger()
    router = ProviderRouter(ledger=ledger)
    for _ in range(5):
        ledger.record(
            UsageEntry(
                provider="google",
                project="gemini-project-a",
                model="test",
                request_id="x",
                timestamp=utc_now(),
                status="ok",
                estimated_cost=router.hard_budget_stop_usd / 4,
            )
        )
    assert router.budget_exhausted()
    gated = GeminiClient(router=router, ledger=ledger)
    stopped = gated.generate("budget", tools=[{"name": "x"}])
    assert stopped.is_fallback
    assert stopped.routing_reason == "hard_budget_stop"
    print("[OK] Hard budget stop prevents further model spend")

    # 3. Routing events preserve reason
    events: list[dict] = []
    obs = ObservabilityService()
    r2 = ProviderRouter(ledger=UsageLedger(), on_routing_event=obs.record_routing_event)
    r2.mark_failure("gemini-project-a", reason="http_429")
    ops = obs.list_events("OPS")
    assert any(e.get("event_type") == "ROUTING_EVENT" for e in ops)
    assert any("http_429" in (e.get("message") or "") for e in ops)
    print("[OK] ROUTING_EVENT records failover reason")

    # 4. Concurrent same-lead investigations stay consistent
    service = InvestigationService(gemini_client=GeminiClient(api_key=""))
    leads = service.list_leads()
    cycle = next(l for l in leads if l.detector_id == "DET-ROUND-TRIP-CYCLE")

    def _run() -> str:
        result = service.start_investigation(cycle.lead_id)
        return result["case"]["case_id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        case_ids = list(pool.map(lambda _: _run(), range(4)))
    assert len(set(case_ids)) == 1
    print("[OK] Concurrent investigations serialize per lead")

    # 5. API ready + metrics + pagination
    api = TestClient(create_app(use_database=False))
    ready = api.get("/ready").json()
    assert ready["status"] == "ready"
    metrics = api.get("/api/metrics").json()
    assert "routing" in metrics and "budgets" in metrics
    leads_page = api.get("/api/leads", params={"limit": 1, "offset": 0}).json()
    assert len(leads_page) == 1
    print("[OK] /ready, /api/metrics, and lead pagination work")

    # 6. Events retain full hashes across investigation
    inv = api.post(
        "/api/investigations/start",
        json={"lead_id": leads_page[0]["lead_id"] if leads_page[0]["detector_id"] == "DET-ROUND-TRIP-CYCLE" else cycle.lead_id},
    )
    # Prefer canonical cycle lead
    cycle_lead = next(l for l in api.get("/api/leads").json() if l["detector_id"] == "DET-ROUND-TRIP-CYCLE")
    inv = api.post("/api/investigations/start", json={"lead_id": cycle_lead["lead_id"]}).json()
    case_id = inv["case"]["case_id"]
    events = api.get("/api/events", params={"case_id": case_id, "limit": 50}).json()
    assert events
    hashed = [e for e in events if e.get("result_hash")]
    assert hashed, "expected full result hashes on investigation step events"
    assert all(len(e["result_hash"]) == 64 for e in hashed)
    print("[OK] Investigation events expose full result hashes")

    print("\nALL RECOVERY CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as err:
        print(f"[FAIL] {err}", file=sys.stderr)
        raise SystemExit(1)
