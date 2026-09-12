"""Provider routing and the usage ledger (orchestrator/routing/).

TASK-007 requires two things of this layer: every routing decision is
logged as `ROUTING_EVENT from/to/reason`, and every call is recorded
against `orchestrator/policies/usage-ledger.schema.json`. Both are
asserted here against the real policy file and the real schema.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.routing.ledger import UsageLedger
from orchestrator.routing.router import (
    Provider,
    ProviderRouter,
    RoutingEvent,
    _parse_minimal_yaml,
    parse_provider_pool,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "orchestrator" / "policies" / "provider-pool.yaml"
LEDGER_SCHEMA = REPO_ROOT / "orchestrator" / "policies" / "usage-ledger.schema.json"


class TestPolicyParsing:
    def test_the_real_pool_file_is_read(self):
        data = parse_provider_pool(POLICY.read_text(encoding="utf-8"))
        assert len(data["providers"]) == 4
        assert data["hard_budget_stop_usd"] == 280
        assert {p["id"] for p in data["providers"]} == {
            f"gemini-project-{letter}" for letter in "abcd"
        }

    def test_the_fallback_parser_agrees_with_pyyaml(self):
        """The worker must start on a machine without PyYAML, and must
        read the same budgets either way -- a parser that quietly
        mis-reads a budget limit is worse than one that refuses."""
        text = POLICY.read_text(encoding="utf-8")
        assert _parse_minimal_yaml(text) == parse_provider_pool(text)

    def test_comments_and_blank_lines_are_ignored(self):
        data = _parse_minimal_yaml(
            "# a comment\n\nproviders:\n  - id: x\n    provider: google\n\nhard_budget_stop_usd: 10\n"
        )
        assert data["providers"] == [{"id": "x", "provider": "google"}]
        assert data["hard_budget_stop_usd"] == 10

    def test_a_missing_policy_file_yields_an_empty_router(self):
        router = ProviderRouter.from_policy(Path("/nonexistent/provider-pool.yaml"))
        assert router.providers == []


class TestRoutingEvents:
    def setup_method(self):
        self.logged: list[str] = []
        self.router = ProviderRouter.from_policy(POLICY, logger=self.logged.append)
        self.router.register(Provider(id="claude-code-cli", provider="anthropic"))

    def test_every_selection_is_logged_not_just_switches(self):
        """The log must answer 'who served this task?' on its own, without
        replaying earlier events to infer the current provider."""
        self.router.select("claude-code-cli", reason="TASK-001:feature:tier1")
        assert len(self.logged) == 1
        assert self.logged[0].startswith("ROUTING_EVENT ")

    def test_event_format_carries_from_to_and_reason(self):
        self.router.select("claude-code-cli", reason="first")
        self.router.select("gemini-project-a", reason="failover")
        rendered = self.logged[1]
        assert "from=claude-code-cli" in rendered
        assert "to=gemini-project-a" in rendered
        assert "reason=failover" in rendered

    def test_the_first_selection_records_no_previous_provider(self):
        self.router.select("claude-code-cli", reason="first")
        assert "from=none" in self.logged[0]

    def test_an_unauthorized_provider_is_refused(self):
        """The router only ever selects providers the team has budget for."""
        with pytest.raises(KeyError) as caught:
            self.router.select("some-other-vendor", reason="cheaper")
        assert "authorized pool" in str(caught.value)

    def test_events_are_retained_for_the_handoff(self):
        self.router.select("claude-code-cli", reason="a")
        self.router.select("gemini-project-b", reason="b")
        assert [event.render() for event in self.router.events] == self.logged

    def test_budget_stop(self):
        assert self.router.budget_exceeded(280.0)
        assert self.router.budget_exceeded(300.0)
        assert not self.router.budget_exceeded(279.99)

    def test_registering_is_idempotent(self):
        before = len(self.router.providers)
        self.router.register(Provider(id="claude-code-cli", provider="anthropic"))
        assert len(self.router.providers) == before


class TestUsageLedger:
    def schema(self):
        return json.loads(LEDGER_SCHEMA.read_text(encoding="utf-8"))

    def test_entries_conform_to_the_frozen_schema(self, tmp_path):
        schema = self.schema()
        ledger = UsageLedger(tmp_path / "usage.jsonl")
        entry = ledger.record(
            provider="anthropic", project="claude-code-cli", model="default",
            input_tokens=120, output_tokens=340, estimated_cost=0.02,
        ).to_dict()

        assert set(schema["required"]) <= set(entry)
        assert set(entry) <= set(schema["properties"]), "no property outside the schema"
        assert entry["status"] in schema["properties"]["status"]["enum"]

    def test_rows_are_appended_one_per_line(self, tmp_path):
        path = tmp_path / "usage.jsonl"
        ledger = UsageLedger(path)
        ledger.record(provider="anthropic", project="claude-code-cli", model="m")
        ledger.record(provider="anthropic", project="claude-code-cli", model="m", status="error",
                      error="timeout")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 2
        assert rows[1]["status"] == "error"
        assert rows[1]["error"] == "timeout"

    def test_unreported_cost_stays_null_rather_than_being_invented(self):
        """A fabricated number in a budget ledger is worse than a gap."""
        entry = UsageLedger(dry_run=True).record(
            provider="anthropic", project="claude-code-cli", model="m"
        ).to_dict()
        assert entry["estimated_cost"] is None
        assert entry["input_tokens"] is None

    def test_an_invalid_status_is_coerced_to_error_not_to_ok(self):
        entry = UsageLedger(dry_run=True).record(
            provider="anthropic", project="p", model="m", status="weird"
        ).to_dict()
        assert entry["status"] == "error"

    def test_dry_run_writes_nothing_to_disk(self, tmp_path):
        path = tmp_path / "usage.jsonl"
        ledger = UsageLedger(path, dry_run=True)
        ledger.record(provider="anthropic", project="p", model="m")
        assert not path.exists()
        assert len(ledger.entries) == 1

    def test_request_ids_are_generated_when_absent(self):
        ledger = UsageLedger(dry_run=True)
        first = ledger.record(provider="a", project="p", model="m")
        second = ledger.record(provider="a", project="p", model="m")
        assert first.request_id and second.request_id
        assert first.request_id != second.request_id

    def test_total_cost_sums_reported_costs_only(self):
        ledger = UsageLedger(dry_run=True)
        ledger.record(provider="a", project="p", model="m", estimated_cost=1.5)
        ledger.record(provider="a", project="p", model="m")
        ledger.record(provider="a", project="p", model="m", estimated_cost=0.25)
        assert ledger.total_cost() == pytest.approx(1.75)


class TestRoutingEventRendering:
    def test_render(self):
        event = RoutingEvent(from_provider="", to_provider="claude-code-cli", reason="start")
        assert event.render() == "ROUTING_EVENT from=none to=claude-code-cli reason=start"
