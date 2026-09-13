"""Bootstrap baseline: every JSON Schema contract must be well-formed.

No product code exists yet (PROJECT_STATE.md), so this is intentionally
the whole baseline test suite for this phase. It validates
domain/schemas/*.schema.json (docs/contracts/domain.md and friends) are
syntactically valid and carry the metadata every contract must have.
"""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "backend" / "src" / "truelock" / "domain" / "schemas"

REQUIRED_TOP_LEVEL_KEYS = {"$schema", "$id", "title", "description", "type"}


def _schema_files():
    return sorted(SCHEMAS_DIR.glob("*.schema.json"))


@pytest.mark.parametrize("schema_path", _schema_files(), ids=lambda p: p.name)
def test_schema_is_valid_json(schema_path):
    with schema_path.open() as f:
        json.load(f)  # raises if malformed


@pytest.mark.parametrize("schema_path", _schema_files(), ids=lambda p: p.name)
def test_schema_has_required_metadata(schema_path):
    with schema_path.open() as f:
        schema = json.load(f)
    missing = REQUIRED_TOP_LEVEL_KEYS - schema.keys()
    assert not missing, f"{schema_path.name} is missing required keys: {missing}"
    assert schema["type"] == "object"
    assert isinstance(schema.get("required", []), list)


def test_at_least_the_expected_schemas_exist():
    names = {p.name for p in _schema_files()}
    expected = {
        "entity.schema.json",
        "provider.schema.json",
        "account.schema.json",
        "invoice.schema.json",
        "payment.schema.json",
        "transaction.schema.json",
        "detector_signal.schema.json",
        "lead.schema.json",
        "evidence.schema.json",
        "investigation_step.schema.json",
        "case.schema.json",
    }
    missing = expected - names
    assert not missing, f"expected schema files missing: {missing}"


def test_lead_schema_requires_discard_reason_when_discarded():
    """domain/contracts/leads.md: a DISCARDED lead must carry a citable
    discard_reason - never a silent discard."""
    with (SCHEMAS_DIR / "lead.schema.json").open() as f:
        schema = json.load(f)
    conditional = schema["allOf"][0]
    assert conditional["if"]["properties"]["status"]["const"] == "DISCARDED"
    assert "discard_reason" in conditional["then"]["required"]
