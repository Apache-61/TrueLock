# database/migrations/

**Purpose:** versioned, forward-only SQL migrations. `0001_init.sql` and
`0002_payment_transaction_ids.sql` are legacy compatibility tables. The
production source of truth is the forward-only canonical `truelock` schema
introduced by migrations `0003` through `0009`.

**What goes here:** `NNNN_description.sql` files, never edited once
applied anywhere -- a change is a new migration.

**What does not go here:** seed/fixture data (-> `database/seeds/`).

**A migration that affects existing data requires human authorization**
(`CONTRIBUTING.md` section 5).

## Applying migrations

Use the migration runner. It records canonical migrations in
`truelock.schema_migrations` and does not reapply them:

```bash
bash scripts/migrate.sh
```

Do not edit an already-applied migration; add a new numbered migration for
any schema change. Demo data is explicitly loaded with
`bash scripts/seed_demo.sh`, never during migration.

`0008_persistence_and_idempotency.sql` adds investigation/import keys
(`external_lead_key`, `idempotency_key`, `related_payment_external_id`,
`external_payment_id`) required by the agent persistence path.

`0009_operational_events_external_key.sql` adds `external_case_key` so
demo/API case ids can persist operational events without a UUID case row.
