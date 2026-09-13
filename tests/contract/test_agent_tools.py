"""Contract tests for agent tool response envelopes."""
from __future__ import annotations

from truelock.agent.tools import ENVELOPE_KEYS, TOOL_DEFINITIONS, ToolRegistry, validate_tool_args
from truelock.seeder.demo_scenario import load_demo_scenario

ENVELOPE_KEY_SET = set(ENVELOPE_KEYS)


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


def _assert_envelope(payload: dict) -> None:
    assert set(payload.keys()) >= ENVELOPE_KEY_SET
    assert isinstance(payload["source_ids"], list)
    assert isinstance(payload["execution_time"], (int, float))
    assert "provenance" in payload


def test_every_tool_definition_has_required_schema_fields():
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "OBJECT"
        assert "properties" in tool["parameters"]
        assert "required" in tool["parameters"]


def test_all_five_tools_return_full_envelope():
    registry = _registry()
    calls = [
        ("trace_outgoing_funds", {"account_id": "012180000000000001", "max_depth": 3}),
        ("inspect_counterparties", {"rfcs": ["CPR190515BB2"]}),
        ("inspect_invoices", {"provider_rfc": "CPR190515BB2"}),
        ("check_regulatory_status", {"rfc": "LSF200820CC3"}),
        (
            "calculate_exposure",
            {
                "root_transaction_id": "TX-ROOT-001",
                "returned_transaction_id": "TX-RET-001",
            },
        ),
    ]
    for name, args in calls:
        payload = registry.execute(name, args)
        _assert_envelope(payload)
        assert payload["errors"] is None
        assert payload["result"] is not None


def test_trace_outgoing_funds_envelope_and_source_ids():
    registry = _registry()
    payload = registry.execute(
        "trace_outgoing_funds",
        {"account_id": "012180000000000001", "max_depth": 3},
    )
    _assert_envelope(payload)
    assert payload["errors"] is None
    assert "TX-ROOT-001" in payload["source_ids"]
    assert "TX-HOP-001" in payload["source_ids"]
    assert payload["provenance"]
    assert len(payload["source_ids"]) == len(set(payload["source_ids"]))


def test_error_responses_still_use_envelope():
    registry = _registry()
    payload = registry.execute("trace_outgoing_funds", {})
    _assert_envelope(payload)
    assert payload["result"] is None
    assert payload["errors"]
    assert payload["source_ids"] == []


def test_undeclared_keys_are_rejected():
    args, err = validate_tool_args(
        "trace_outgoing_funds",
        {"account_id": "012180000000000001", "extra_field": "nope"},
    )
    assert args is None
    assert err is not None
    assert "Undeclared" in err

    registry = _registry()
    payload = registry.execute(
        "inspect_counterparties",
        {"rfcs": ["CPR190515BB2"], "limit": 5},
    )
    assert payload["errors"] is not None
    assert "Undeclared" in payload["errors"]


def test_aliases_normalized_and_not_forwarded():
    args, err = validate_tool_args(
        "trace_outgoing_funds",
        {"account_no": "012180000000000001", "depth": 2},
    )
    assert err is None
    assert args == {"account_id": "012180000000000001", "max_depth": 2}
    assert "account_no" not in args
    assert "depth" not in args


def test_invalid_types_rejected():
    args, err = validate_tool_args(
        "inspect_counterparties",
        {"rfcs": "CPR190515BB2"},
    )
    assert args is None
    assert err is not None
    assert "array" in err.lower()


def test_calculate_exposure_envelope():
    registry = _registry()
    payload = registry.execute(
        "calculate_exposure",
        {
            "root_transaction_id": "TX-ROOT-001",
            "returned_transaction_id": "TX-RET-001",
        },
    )
    _assert_envelope(payload)
    assert payload["errors"] is None
    assert payload["result"]["supported_exposure"] == 1_000_000.0
    assert payload["result"]["net_exposure"] == 260_000.0
    assert payload["source_ids"] == ["TX-ROOT-001", "TX-RET-001"]
    assert payload["result"]["policy"] == "ROOT_FLOW_UNDUPLICATED_WITH_RETURN_OFFSET"


def test_max_depth_is_capped_at_five():
    registry = _registry()
    payload = registry.execute(
        "trace_outgoing_funds",
        {"account_id": "012180000000000001", "max_depth": 99},
    )
    assert payload["errors"] is None
    assert payload["result"]["depth_limit"] == 5
    assert payload["result"]["depth_reached"] <= 5
