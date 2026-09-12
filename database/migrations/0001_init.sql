-- TrueLock — initial schema.
-- Mirrors domain/schemas/*.schema.json — see docs/contracts/domain.md.
-- Any structural change here that affects existing data requires human
-- authorization (CONTRIBUTING.md §5) and a new migration file, never an
-- edit to this one once applied anywhere.

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,
    rfc         VARCHAR(13),
    name        TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('company', 'individual'))
);

CREATE TABLE IF NOT EXISTS providers (
    rfc                 VARCHAR(13) PRIMARY KEY,
    name                TEXT NOT NULL,
    registration_date   DATE,
    address             TEXT,
    phone               TEXT,
    efos_status         TEXT NOT NULL DEFAULT 'UNKNOWN'
        CHECK (efos_status IN ('PRESUMED', 'DEFINITIVE', 'INVALIDATED', 'FAVORABLE_JUDGMENT', 'UNKNOWN')),
    efos_listed_date    DATE
    -- See domain/enums/efos-status.md: efos_status is fiscal evidence,
    -- never treated as a fraud label by itself.
);

CREATE TABLE IF NOT EXISTS accounts (
    account_no  VARCHAR(32) PRIMARY KEY,
    entity_id   TEXT NOT NULL REFERENCES entities(id),
    bank        TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    uuid            UUID PRIMARY KEY,
    version         TEXT DEFAULT '4.0',
    provider_rfc    VARCHAR(13) NOT NULL REFERENCES providers(rfc),
    receiver_rfc    VARCHAR(13) NOT NULL,
    issue_date      DATE NOT NULL,
    amount          NUMERIC(14, 2) NOT NULL,
    subtotal        NUMERIC(14, 2),
    taxes           NUMERIC(14, 2),
    currency        VARCHAR(3) DEFAULT 'MXN',
    payment_method  TEXT,
    payment_form    TEXT,
    cfdi_type       TEXT,
    concept         TEXT
);

-- INVOICE -> PAYMENT -> TRANSACTION stay distinct layers.
-- See docs/contracts/domain.md, "why three layers, not one".
CREATE TABLE IF NOT EXISTS payments (
    id                      TEXT PRIMARY KEY,
    related_invoice_uuid    UUID NOT NULL REFERENCES invoices(uuid),
    payment_date            DATE NOT NULL,
    amount                  NUMERIC(14, 2) NOT NULL,
    payment_form            TEXT,
    currency                VARCHAR(3) DEFAULT 'MXN',
    previous_balance        NUMERIC(14, 2),
    remaining_balance       NUMERIC(14, 2)
);

CREATE TABLE IF NOT EXISTS transactions (
    id                  TEXT PRIMARY KEY,
    from_account        VARCHAR(32) NOT NULL REFERENCES accounts(account_no),
    to_account          VARCHAR(32) NOT NULL REFERENCES accounts(account_no),
    transaction_date    DATE NOT NULL,
    amount              NUMERIC(14, 2) NOT NULL,
    related_payment_id  TEXT REFERENCES payments(id)
    -- related_payment_id may be NULL: a bare fund movement with no invoice
    -- behind it (e.g. layering between shell accounts) is often the most
    -- evidentially important kind. See docs/detection/rules.md.
);

-- The final case file is stored as JSONB here instead of a separate
-- document store (see history/decisions/ADR-0004-sponsor-tech-scope.md
-- re: MongoDB decision).
CREATE TABLE IF NOT EXISTS case_files (
    case_id             TEXT PRIMARY KEY,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status              TEXT NOT NULL CHECK (status IN ('SUBSTANTIATED', 'UNSUBSTANTIATED', 'INSUFFICIENT_EVIDENCE')),
    confidence_level    TEXT NOT NULL CHECK (confidence_level IN ('LOW', 'MEDIUM', 'HIGH')),
    amount_involved     NUMERIC(14, 2) NOT NULL,
    content             JSONB NOT NULL,     -- full Case object, domain/schemas/case.schema.json
    evidence_hash       TEXT,               -- SHA-256 of the canonical serialization, for optional Solana notarization
    solana_tx_signature TEXT                -- NULL unless notarized
);

CREATE INDEX IF NOT EXISTS idx_invoices_provider ON invoices(provider_rfc);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(related_invoice_uuid);
CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_account);
CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_account);
CREATE INDEX IF NOT EXISTS idx_transactions_payment ON transactions(related_payment_id);
