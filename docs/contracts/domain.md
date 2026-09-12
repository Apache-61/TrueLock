# Contract: Domain model

Canonical data model, shared by every module. JSON Schema source of truth:
`domain/schemas/*.schema.json`. Regulatory grounding: `research/sat/README.md`.

## Why three layers, not one "financial transaction"

```
INVOICE  →  PAYMENT  →  TRANSACTION
```

SAT's payment-complement model exposes payment date, form, currency,
amount, related invoice UUID, installment info, and balances as distinct
from both the invoice and the underlying bank movement. Collapsing these
into one record loses exactly the distinctions a forensic investigation
needs: an invoice can be issued and never paid (a signal on its own); a
payment can settle via multiple transactions or partial installments; a
transaction can exist with no invoice behind it at all (e.g. a shell
company forwarding funds it just received — this is often where the real
evidence is). See `docs/detection/rules.md` → "rapid pass-through".

## Entities

| Entity | Schema | Key fields |
|---|---|---|
| Entity (person/company) | `domain/schemas/entity.schema.json` | id, rfc, entity_type |
| Provider | `domain/schemas/provider.schema.json` | rfc, efos_status |
| Account | `domain/schemas/account.schema.json` | account_no, entity_id |
| Invoice (CFDI) | `domain/schemas/invoice.schema.json` | uuid, provider_rfc, receiver_rfc, amount |
| Payment | `domain/schemas/payment.schema.json` | id, related_invoice_uuid, amount |
| Transaction | `domain/schemas/transaction.schema.json` | id, from_account, to_account, amount |

## Graph edges built from these entities

```
COMPANY  --ISSUED-->      INVOICE
SUPPLIER --ISSUED-->      INVOICE
INVOICE  --PAID_BY-->     PAYMENT
PAYMENT  --SETTLED_AS-->  TRANSACTION
ACCOUNT  --SENT-->        TRANSACTION
TRANSACTION --TO-->       ACCOUNT
COMPANY  --OWNS/USES-->   ACCOUNT
```

See `research/graph/README.md` and `detection/graph/README.md`.

## EFOS status

See `domain/enums/efos-status.md`. Modeled as fiscal status, never
auto-equated with fraud.

## Who owns this contract

Agent B (Data/Backend) drafts changes; any change requires human
authorization per `CONTRIBUTING.md` §5, because `detection/`, `agent/`,
`backend/`, and `frontend/` all consume it directly.
