"""Contract tests for agent tool response envelopes."""
from __future__ import annotations

from truelock.agent.tools import TOOL_DEFINITIONS, ToolRegistry
from truelock.seeder.demo_scenario import load_demo_scenario

ENVELOPE_KEYS = {"result", "provenance", "source_ids", "execution_time", "errors"}


def _registry() -> ToolRegistry:
    repo = load_demo_scenario()
    return ToolRegistry(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )


def test_every_tool_definition_has_required_schema_fields():
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "OBJECT"
        assert "properties" in tool["parameters"]
        assert "required" in tool["parameters"]


def test_trace_outgoing_funds_envelope_and_source_ids():
    registry = _registry()
    payload = registry.execute(
        "trace_outgoing_funds",
        {"account_id": "012180000000000001", "max_depth": 3},
    )
    assert set(payload.keys()) >= ENVELOPE_KEYS
    assert payload["errors"] is None
    assert isinstance(payload["source_ids"], list)
    assert "TX-ROOT-001" in payload["source_ids"]
    assert "TX-HOP-001" in payload["source_ids"]
    assert payload["provenance"]


def test_error_responses_still_use_envelope():
    registry = _registry()
    payload = registry.execute("trace_outgoing_funds", {})
    assert set(payload.keys()) >= ENVELOPE_KEYS
    assert payload["result"] is None
    assert payload["errors"]
    assert payload["source_ids"] == []


def test_calculate_exposure_envelope():
    registry = _registry()
    payload = registry.execute(
        "calculate_exposure",
        {
            "root_transaction_id": "TX-ROOT-001",
            "returned_transaction_id": "TX-RET-001",
        },
    )
    assert set(payload.keys()) >= ENVELOPE_KEYS
    assert payload["errors"] is None
    assert payload["result"]["supported_exposure"] == 1_000_000.0
    assert payload["result"]["net_exposure"] == 260_000.0
    assert payload["source_ids"] == ["TX-ROOT-001", "TX-RET-001"]


def test_max_depth_is_capped_at_five():
    registry = _registry()
    payload = registry.execute(
        "trace_outgoing_funds",
        {"account_id": "012180000000000001", "max_depth": 99},
    )
    assert payload["errors"] is None
    assert payload["result"]["depth_reached"] == 5
