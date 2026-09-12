# database/migrations/

**Purpose:** versioned, forward-only SQL migrations. `0001_init.sql` is
the initial schema mirroring `domain/schemas/`; `0002_payment_transaction_ids.sql`
adds the `Payment.transaction_ids` field from the canonical entity.

**What goes here:** `NNNN_description.sql` files, never edited once
applied anywhere -- a change is a new migration.

**What does not go here:** seed/fixture data (-> `database/seeds/`).

**A migration that affects existing data requires human authorization**
(`CONTRIBUTING.md` section 5).

## Applying migrations

Run every `*.sql` file in lexical filename order with `ON_ERROR_STOP=1`.
The scripts use `IF NOT EXISTS`, so an interrupted or repeated application
is safe:

```bash
for migration in database/migrations/*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"
done
```

`0002_payment_transaction_ids.sql` has a documented forward path: apply it
after `0001_init.sql`; do not edit an already-applied migration to change
the schema.
