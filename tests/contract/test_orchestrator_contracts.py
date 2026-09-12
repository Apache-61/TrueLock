"""Contract tests for the orchestrator's own interfaces.

Same standard the domain contracts are held to (`tests/contract/test_schemas.py`):
the schema files are well-formed and carry their metadata, and -- the part
that actually catches drift -- the objects the worker emits still validate
against them.

Validation is done with a small structural checker rather than
`jsonschema`, because adding a dependency needs human authorization
(`CONTRIBUTING.md` §5) and the shapes here are simple enough that the
checker is shorter than the argument for the library.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.routing.ledger import UsageLedger
from orchestrator.workers.adapters.base import result_from_dict
from orchestrator.workers.handoff import Handoff

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICIES = REPO_ROOT / "orchestrator" / "policies"
TASK_RESULT_SCHEMA = POLICIES / "task-result.schema.json"
USAGE_LEDGER_SCHEMA = POLICIES / "usage-ledger.schema.json"

REQUIRED_TOP_LEVEL_KEYS = {"$schema", "$id", "title", "description", "type"}

JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def check(instance, schema, path="$") -> list[str]:
    """Structural validation: types, required keys, enums, extra keys."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected:
        allowed = expected if isinstance(expected, list) else [expected]
        types = tuple(JSON_TYPES[name] for name in allowed)
        # bool is a subclass of int; JSON Schema treats them as distinct.
        if isinstance(instance, bool) and "boolean" not in allowed:
            errors.append(f"{path}: boolean where {allowed} expected")
            return errors
        if not isinstance(instance, types):
            errors.append(f"{path}: {type(instance).__name__} where {allowed} expected")
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: unexpected key {key!r}")
        for key, value in instance.items():
            if key in properties:
                errors.extend(check(value, properties[key], f"{path}.{key}"))

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(check(item, schema["items"], f"{path}[{index}]"))

    if isinstance(instance, int) and not isinstance(instance, bool) and "minimum" in schema:
        if instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
    return errors


def schema_files():
    return sorted(POLICIES.glob("*.schema.json"))


@pytest.mark.parametrize("path", schema_files(), ids=lambda p: p.name)
def test_policy_schema_is_valid_json_with_metadata(path):
    schema = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TOP_LEVEL_KEYS - schema.keys()
    assert not missing, f"{path.name} is missing {missing}"
    assert schema["type"] == "object"


def test_the_expected_policy_schemas_exist():
    assert {path.name for path in schema_files()} >= {
        "usage-ledger.schema.json",
        "task-result.schema.json",
    }


class TestHandoffMatchesItsSchema:
    def schema(self):
        return json.loads(TASK_RESULT_SCHEMA.read_text(encoding="utf-8"))

    def handoff(self, **kwargs) -> Handoff:
        defaults = dict(
            run_id="AI-RUN-20260912T120000Z-abc123",
            worker_id="WORKER-01",
            task_id="TASK-007",
            issue_number=7,
            branch="feature/TASK-007-worker",
            started_at="2026-09-12T12:00:00+00:00",
            finished_at="2026-09-12T12:30:00+00:00",
            outcome="DONE",
            validation_summary="PASSED -- 5 gate(s) passed, 0 failed, 2 skipped",
            result=result_from_dict({
                "task_id": "TASK-007",
                "status": "DONE",
                "summary": "Built the worker.",
                "changed_files": ["orchestrator/workers/runner.py"],
                "tests": {"passed": 12, "failed": 0, "skipped": 1, "details": "pytest"},
                "next_recommended_tasks": ["TASK-001"],
            }),
        )
        defaults.update(kwargs)
        return Handoff(**defaults)

    def test_a_successful_handoff_validates(self):
        errors = check(self.handoff().to_dict(), self.schema())
        assert errors == [], errors

    @pytest.mark.parametrize("outcome", ["DONE", "BLOCKED", "FAILED", "PROPOSAL", "LOST_CLAIM"])
    def test_every_outcome_validates(self, outcome):
        errors = check(self.handoff(outcome=outcome).to_dict(), self.schema())
        assert errors == [], errors

    def test_a_handoff_with_no_ai_result_still_validates(self):
        """A run that died before the AI answered must still emit a
        readable handoff -- that is the record of what went wrong."""
        errors = check(self.handoff(result=None, outcome="FAILED").to_dict(), self.schema())
        assert errors == [], errors

    def test_the_escalation_fields_validate(self):
        handoff = self.handoff(
            adr_required=["ARCHITECTURE.md"],
            experiment_required=True,
            scope_violations=["`frontend/x.tsx`: outside allowed_paths"],
            routing_events=["ROUTING_EVENT from=none to=claude-code-cli reason=start"],
        )
        errors = check(handoff.to_dict(), self.schema())
        assert errors == [], errors

    def test_the_checker_actually_rejects_a_bad_payload(self):
        """A validator that never fails proves nothing."""
        payload = self.handoff().to_dict()
        payload["status"] = "TOTALLY-MADE-UP"
        payload["changed_files"] = "not-a-list"
        del payload["summary"]
        errors = check(payload, self.schema())
        assert len(errors) >= 3


class TestLedgerMatchesItsSchema:
    def test_entries_validate(self):
        schema = json.loads(USAGE_LEDGER_SCHEMA.read_text(encoding="utf-8"))
        entry = UsageLedger(dry_run=True).record(
            provider="anthropic", project="claude-code-cli", model="default",
            input_tokens=10, output_tokens=20, estimated_cost=0.001,
        ).to_dict()
        assert check(entry, schema) == []

    def test_an_entry_with_no_token_counts_validates(self):
        """The CLI does not always report usage; nulls are in contract,
        invented numbers are not."""
        schema = json.loads(USAGE_LEDGER_SCHEMA.read_text(encoding="utf-8"))
        entry = UsageLedger(dry_run=True).record(
            provider="anthropic", project="claude-code-cli", model="default",
        ).to_dict()
        assert check(entry, schema) == []
