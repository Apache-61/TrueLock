"""Every canonical entity still matches its JSON Schema.

`domain/schemas/` is the source of truth and `domain/entities/` mirrors
it (TASK-001, `domain/entities/README.md`). Nothing enforces that
mirroring at runtime, so this does — field by field, rather than trusting
it to review.

The drift this catches is quiet: a schema gains a field, the entity does
not, and ingestion silently drops it. Because `extra="forbid"` only
rejects fields the *model* does not know, a schema-only field produces no
error anywhere — records just arrive missing data, and a detector later
reports "no signal" instead of "I could not see that column".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from truelock.domain.models import CANONICAL_ENTITIES

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "backend" / "src" / "truelock" / "domain" / "schemas"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


ENTITY_NAMES = sorted(CANONICAL_ENTITIES)


def test_every_canonical_schema_has_an_entity():
    """TASK-001 acceptance criterion 1, checked against the directory."""
    investigation_layer = {  # TASK-008, not TASK-001
        "case", "detector_signal", "evidence", "investigation_step", "lead",
    }
    on_disk = {
        path.name.replace(".schema.json", "")
        for path in SCHEMA_DIR.glob("*.schema.json")
    } - investigation_layer
    assert on_disk == set(CANONICAL_ENTITIES), (
        "a canonical schema has no entity class (or vice versa); "
        f"schemas={sorted(on_disk)} entities={ENTITY_NAMES}"
    )


@pytest.mark.parametrize("name", ENTITY_NAMES)
class TestEntityMatchesItsSchema:
    def test_every_schema_property_is_a_model_field(self, name):
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        missing = set(schema["properties"]) - set(model.model_fields)
        assert not missing, f"{name}: schema declares {sorted(missing)}, the entity does not"

    def test_the_model_invents_no_field(self, name):
        """An entity field with no schema property cannot round-trip."""
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        extra = set(model.model_fields) - set(schema["properties"])
        assert not extra, f"{name}: entity declares {sorted(extra)}, the schema does not"

    def test_required_fields_are_required(self, name):
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        for field_name in schema.get("required", []):
            assert model.model_fields[field_name].is_required(), (
                f"{name}.{field_name} is required by the schema but optional on the entity"
            )

    def test_optional_fields_are_optional(self, name):
        """Requiring more than the schema rejects records the contract allows."""
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        required = set(schema.get("required", []))
        for field_name, field in model.model_fields.items():
            if field_name not in required:
                assert not field.is_required(), (
                    f"{name}.{field_name} is optional in the schema but required "
                    "on the entity"
                )

    def test_additional_properties_are_forbidden_both_sides(self, name):
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        assert schema.get("additionalProperties") is False, (
            f"{name}.schema.json should forbid additional properties"
        )
        assert model.model_config.get("extra") == "forbid", (
            f"{name} entity must reject unknown fields, not ignore them"
        )

    def test_enum_values_match(self, name):
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        for field_name, spec in schema["properties"].items():
            if "enum" not in spec:
                continue
            annotation = model.model_fields[field_name].annotation
            members = getattr(annotation, "__members__", None)
            assert members is not None, (
                f"{name}.{field_name} is an enum in the schema but not on the entity"
            )
            assert {member.value for member in members.values()} == set(spec["enum"]), (
                f"{name}.{field_name} enum values have drifted from the schema"
            )

    def test_schema_defaults_match_entity_defaults(self, name):
        schema = load_schema(name)
        model = CANONICAL_ENTITIES[name]
        for field_name, spec in schema["properties"].items():
            if "default" not in spec:
                continue
            field = model.model_fields[field_name]
            assert field.default == spec["default"], (
                f"{name}.{field_name} defaults to {field.default!r}, "
                f"the schema says {spec['default']!r}"
            )
