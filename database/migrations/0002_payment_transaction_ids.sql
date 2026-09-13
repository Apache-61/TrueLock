-- Add the canonical Payment.transaction_ids field.
-- Forward path: apply after 0001_init.sql; this migration is safe to
-- re-run because the column is added only when it is absent.
-- The schema change requires human authorization under CONTRIBUTING.md section 5.

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS transaction_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
