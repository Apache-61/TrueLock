"""E2E: inject-fraud + offline fallback + eval promotion gate."""
from __future__ import annotations

from starlette.testclient import TestClient

from truelock.agent.eval import promotion_gate
from truelock.api.app import create_app


def test_inject_fraud_then_investigate_offline() -> None:
    client = TestClient(create_app(use_database=False))
    injected = client.post(
        "/demo/inject-fraud",
        json={"scenario_id": "hidden_pass_through"},
    ).json()
    assert injected["scenario_id"] == "hidden_pass_through"

    leads = client.get("/api/leads").json()
    assert any(
        lead["detector_id"] in {"DET-RAPID-PASS-THROUGH", "DET-ROUND-TRIP-CYCLE"}
        for lead in leads
    )
    # Prefer injected pass-through account if present
    target = next(
        (l for l in leads if "HIDDEN" in l.get("lead_id", "") or "PASSTHROUGH" in l.get("lead_id", "")),
        max(leads, key=lambda item: item["risk_score"]),
    )
    inv = client.post("/api/investigations/start", json={"lead_id": target["lead_id"]}).json()
    assert inv["steps"]
    # Offline Gemini must still produce real source refs, not invented ones
    for evidence in inv["evidence"]:
        assert evidence.get("source_id")
        assert not str(evidence["source_id"]).startswith("TX-INVENTED")


def test_offline_health_and_events() -> None:
    client = TestClient(create_app(use_database=False))
    health = client.get("/health").json()
    assert health["status"] in {"ok", "degraded"} or "gemini" in health

    leads = client.get("/api/leads").json()
    cycle = next(l for l in leads if l["detector_id"] == "DET-ROUND-TRIP-CYCLE")
    inv = client.post("/api/investigations/start", json={"lead_id": cycle["lead_id"]}).json()
    events = client.get("/api/events", params={"case_id": inv["case"]["case_id"]}).json()
    assert isinstance(events, list)


def test_eval_promotion_gate_blocks_regressions() -> None:
    """Exit criterion: blocked eval set fails closed on invented sources / bad exposure / false accuse."""
    passed, results = promotion_gate("eval")
    assert results, "eval corpus must not be empty"
    assert passed, {
        item.corpus_id: item.failures for item in results if not item.gates_passed
    }
