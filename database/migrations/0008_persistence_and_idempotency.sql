-- Persistence helpers for agent investigation writes and import idempotency.
-- Immutable forward migration; do not edit after apply.

ALTER TABLE truelock.bank_transactions
    ADD COLUMN IF NOT EXISTS related_payment_external_id text;

CREATE UNIQUE INDEX IF NOT EXISTS bank_transactions_case_external_id_uq
    ON truelock.bank_transactions (case_id, external_transaction_id)
    WHERE external_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS bank_transactions_related_payment_idx
    ON truelock.bank_transactions (case_id, related_payment_external_id)
    WHERE related_payment_external_id IS NOT NULL;

ALTER TABLE truelock.leads
    ADD COLUMN IF NOT EXISTS external_lead_key text;

CREATE UNIQUE INDEX IF NOT EXISTS leads_case_external_key_uq
    ON truelock.leads (case_id, external_lead_key)
    WHERE external_lead_key IS NOT NULL;

ALTER TABLE truelock.investigations
    ADD COLUMN IF NOT EXISTS idempotency_key text,
    ADD COLUMN IF NOT EXISTS dataset_fingerprint text;

CREATE UNIQUE INDEX IF NOT EXISTS investigations_case_idempotency_uq
    ON truelock.investigations (case_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

ALTER TABLE truelock.payment_complements
    ADD COLUMN IF NOT EXISTS external_payment_id text;

CREATE UNIQUE INDEX IF NOT EXISTS payment_complements_case_external_id_uq
    ON truelock.payment_complements (case_id, external_payment_id)
    WHERE external_payment_id IS NOT NULL;

INSERT INTO truelock.schema_migrations(version)
VALUES ('0008_persistence_and_idempotency');
