# domain/entities/

**Purpose:** language-level implementations of the JSON Schema contracts
in `domain/schemas/` — Pydantic models for the backend.

**What goes here:** typed classes mirroring a schema 1:1, plus their
(de)serialization. No business logic beyond validation.

**What does not go here:** detection rules (`detection/rules/`), the JSON
Schema itself (`domain/schemas/`, the source of truth — these must not
drift from it), agent behaviour (`agent/`).

**Depends on:** `domain/schemas/*.schema.json`.

## Implemented (TASK-001)

The six canonical records — what the source data says:

| Entity | Schema | Notes |
|---|---|---|
| `Entity` | `entity.schema.json` | company or individual; `rfc` nullable |
| `Provider` | `provider.schema.json` | supplier + SAT 69-B/EFOS status |
| `Invoice` | `invoice.schema.json` | canonical CFDI 4.0 subset |
| `Payment` | `payment.schema.json` | payment-complement settlement |
| `Transaction` | `transaction.schema.json` | bank movement; the graph's edge |
| `Account` | `account.schema.json` | bank account; the graph's node |

The investigation layer — `Lead`, `Evidence`, `InvestigationStep`,
`Case` — is **TASK-008** and lands alongside these.

## The validation stance

`base.py` sets it once for every entity, and it is deliberately
unforgiving: **a record we do not understand is rejected, not repaired.**

- `extra="forbid"` — an unexpected field is an error, not something to
  ignore. A CFDI carrying a field we have never seen may be a newer
  version, a different variant, or a forgery; none of those should be
  ingested minus the part nobody read.
- `frozen=True` — an entity records what a source said. Code that wants
  to change it is making a new record and should say so.
- Explicit types — an ISO date string becomes a `date`; a non-date string
  fails rather than becoming today.

The failure this prevents is specific: a forensic conclusion resting on a
field that was silently coerced or defaulted is worse than no conclusion,
because it looks equally confident. `SECURITY.md` is the policy;
`domain/entities/base.py` is where it is enforced.

Two normalizations *are* applied, because both lose nothing and skipping
either breaks joins silently:

- RFCs are upper-cased — otherwise `ABC010101AAA` and `abc010101aaa`
  become two suppliers, defeating every concentration and duplicate rule.
- A CFDI `Fecha` datetime is truncated to the contract's `date`.

## Using them

```python
from domain.entities import Invoice, EntityValidationError

try:
    invoice = Invoice.parse(record)        # raises on anything malformed
except EntityValidationError as error:
    print(error)                           # names the entity and the field

invoice.to_dict()                          # JSON-shaped; round-trips exactly
```

`Entity.parse(e.to_dict()) == e` holds for every entity and is asserted in
`tests/unit/test_domain_entities.py`.

## Keeping them honest

`tests/contract/test_entity_schema_alignment.py` compares every entity
against its schema field by field — properties, required/optional,
enum values, defaults, and that both sides forbid extra properties.

It exists because the drift is quiet. If a schema gains a field and the
entity does not, `extra="forbid"` raises nothing — it only rejects fields
the *model* does not know. Records simply arrive missing data, and a
detector later reports "no signal" instead of "I could not see that
column".
