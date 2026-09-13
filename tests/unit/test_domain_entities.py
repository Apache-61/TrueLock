"""Canonical entity validation (`domain/entities/`, TASK-001).

The acceptance criteria these cover:

* a malformed record is **rejected with a clear error**, not
  best-effort-guessed (`SECURITY.md`);
* entity -> dict -> entity round-trips to an identical object.

Both matter for the same reason: everything downstream -- detectors,
agent tools, evidence, the case file -- treats these objects as facts
about the source data. A field that was coerced, defaulted or dropped
here becomes a citation in a case file later, and by then nothing
remembers it was a guess.
"""
from __future__ import annotations

from datetime import date

import pytest

from truelock.domain.models import (
    CANONICAL_ENTITIES,
    Account,
    EfosStatus,
    Entity,
    EntityType,
    EntityValidationError,
    Invoice,
    Payment,
    Provider,
    Transaction,
)

VALID_UUID = "123e4567-e89b-12d3-a456-426614174000"

VALID = {
    "account": {"account_no": "ACC-1", "entity_id": "E-1", "bank": "BBVA"},
    "entity": {"id": "E-1", "name": "Acme SA", "entity_type": "company", "rfc": "ABC010101AAA"},
    "invoice": {
        "uuid": VALID_UUID, "provider_rfc": "ABC010101AAA", "receiver_rfc": "XYZ020202BBB",
        "issue_date": "2026-01-15", "amount": 1000.0,
    },
    "payment": {
        "id": "P-1", "related_invoice_uuid": VALID_UUID,
        "payment_date": "2026-01-20", "amount": 1000.0,
    },
    "provider": {"rfc": "ABC010101AAA", "name": "Acme SA", "efos_status": "DEFINITIVE"},
    "transaction": {
        "id": "T-1", "from_account": "ACC-1", "to_account": "ACC-2",
        "transaction_date": "2026-01-20", "amount": 1000.0,
    },
}


class TestRoundTrip:
    @pytest.mark.parametrize("name", sorted(CANONICAL_ENTITIES))
    def test_entity_to_dict_to_entity_is_identical(self, name):
        model = CANONICAL_ENTITIES[name]
        original = model.parse(VALID[name])
        assert model.parse(original.to_dict()) == original

    @pytest.mark.parametrize("name", sorted(CANONICAL_ENTITIES))
    def test_the_dict_is_json_shaped(self, name):
        """Dates as ISO strings, enums as values — what the API serialises."""
        import json

        model = CANONICAL_ENTITIES[name]
        payload = model.parse(VALID[name]).to_dict()
        assert json.loads(json.dumps(payload)) == payload

    def test_optional_fields_survive_the_round_trip(self):
        payment = Payment.parse({
            **VALID["payment"],
            "previous_balance": 500.0,
            "remaining_balance": 0.0,
            "transaction_ids": ["T-1", "T-2"],
        })
        assert Payment.parse(payment.to_dict()) == payment
        assert payment.transaction_ids == ("T-1", "T-2")


class TestMalformedRecordsAreRejected:
    @pytest.mark.parametrize("name", sorted(CANONICAL_ENTITIES))
    def test_an_unknown_field_is_refused_not_ignored(self, name):
        """A record we do not fully understand is not ingested minus the part we missed."""
        model = CANONICAL_ENTITIES[name]
        with pytest.raises(EntityValidationError) as caught:
            model.parse({**VALID[name], "surprise_column": "?"})
        assert "surprise_column" in str(caught.value)

    @pytest.mark.parametrize("name", sorted(CANONICAL_ENTITIES))
    def test_a_missing_required_field_is_refused(self, name):
        model = CANONICAL_ENTITIES[name]
        required = next(iter(VALID[name]))
        record = {key: value for key, value in VALID[name].items() if key != required}
        with pytest.raises(EntityValidationError) as caught:
            model.parse(record)
        assert required in str(caught.value)

    def test_the_error_names_the_entity_and_the_field(self):
        """An error a human can act on without reading a stack trace."""
        with pytest.raises(EntityValidationError) as caught:
            Invoice.parse({**VALID["invoice"], "issue_date": "not-a-date"})
        message = str(caught.value)
        assert message.startswith("Invoice is not valid")
        assert "issue_date" in message

    def test_a_bad_date_is_not_silently_defaulted(self):
        with pytest.raises(EntityValidationError):
            Transaction.parse({**VALID["transaction"], "transaction_date": "15/01/2026"})

    def test_a_malformed_cfdi_uuid_is_refused(self):
        """A bad folio would fail to join silently, reading as 'no duplicates'."""
        with pytest.raises(EntityValidationError) as caught:
            Invoice.parse({**VALID["invoice"], "uuid": "not-a-uuid"})
        assert "UUID" in str(caught.value)

    def test_an_empty_required_string_is_refused(self):
        with pytest.raises(EntityValidationError):
            Account.parse({"account_no": "", "entity_id": "E-1"})

    def test_an_unknown_enum_value_is_refused(self):
        with pytest.raises(EntityValidationError):
            Provider.parse({**VALID["provider"], "efos_status": "PROBABLY_FINE"})

    def test_a_non_numeric_amount_is_refused(self):
        with pytest.raises(EntityValidationError):
            Invoice.parse({**VALID["invoice"], "amount": "a lot"})


class TestNormalization:
    def test_rfcs_are_upper_cased(self):
        """Otherwise one supplier becomes two, defeating every concentration rule."""
        invoice = Invoice.parse({**VALID["invoice"], "provider_rfc": "abc010101aaa"})
        assert invoice.provider_rfc == "ABC010101AAA"

    def test_dates_become_dates(self):
        invoice = Invoice.parse(VALID["invoice"])
        assert invoice.issue_date == date(2026, 1, 15)

    def test_defaults_match_the_contract(self):
        invoice = Invoice.parse(VALID["invoice"])
        assert (invoice.version, invoice.currency) == ("4.0", "MXN")


class TestProviderFiscalStatus:
    def test_a_listing_date_without_a_listing_is_refused(self):
        """A record that says both 'never listed' and 'listed on this date'."""
        with pytest.raises(EntityValidationError) as caught:
            Provider.parse({
                "rfc": "ABC010101AAA", "name": "Acme",
                "efos_status": "UNKNOWN", "efos_listed_date": "2026-01-01",
            })
        assert "listing" in str(caught.value)

    def test_a_listed_provider_may_carry_its_date(self):
        provider = Provider.parse({
            "rfc": "ABC010101AAA", "name": "Acme",
            "efos_status": "DEFINITIVE", "efos_listed_date": "2026-01-01",
        })
        assert provider.efos_listed_date == date(2026, 1, 1)

    def test_unknown_is_the_default_stance(self):
        """UNKNOWN is distinct from 'not listed': we do not claim what we did not check."""
        assert EfosStatus.UNKNOWN.value == "UNKNOWN"
        provider = Provider.parse({**VALID["provider"], "efos_status": "UNKNOWN"})
        assert provider.efos_status is EfosStatus.UNKNOWN


class TestEntitiesAreImmutable:
    def test_an_entity_cannot_be_edited_in_place(self):
        """An entity records what a source said; changing it makes a new record."""
        entity = Entity.parse(VALID["entity"])
        with pytest.raises(Exception):
            entity.name = "Something else"

    def test_entity_type_is_an_enum(self):
        assert Entity.parse(VALID["entity"]).entity_type is EntityType.COMPANY
