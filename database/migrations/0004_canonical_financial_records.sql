CREATE TYPE truelock.cfdi_type AS ENUM ('I', 'E', 'T', 'N', 'P');
CREATE TYPE truelock.cfdi_status AS ENUM (
    'ACTIVE', 'CANCELLED', 'SUBSTITUTED', 'UNKNOWN', 'NOT_CHECKED'
);
CREATE TYPE truelock.cash_direction AS ENUM ('CREDIT', 'DEBIT', 'UNKNOWN');

CREATE TABLE truelock.invoices (
    invoice_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id),
    source_locator text NOT NULL,
    record_sha256 text CHECK (record_sha256 IS NULL OR truelock.is_sha256(record_sha256)),
    uuid text,
    version text,
    serie text,
    folio text,
    issue_timestamp timestamptz NOT NULL,
    stamped_timestamp timestamptz,
    issuer_entity_id uuid REFERENCES truelock.entities(entity_id),
    receiver_entity_id uuid REFERENCES truelock.entities(entity_id),
    rfc_issuer text NOT NULL,
    issuer_name text,
    issuer_tax_regime text,
    rfc_receiver text NOT NULL,
    receiver_name text,
    receiver_tax_address text,
    receiver_tax_regime text,
    cfdi_use text,
    subtotal numeric(20,6) NOT NULL CHECK (subtotal >= 0),
    discount numeric(20,6) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    tax_total numeric(20,6),
    total numeric(20,6) NOT NULL CHECK (total >= 0),
    currency char(3) NOT NULL,
    exchange_rate numeric(20,10) CHECK (exchange_rate IS NULL OR exchange_rate > 0),
    amount_mxn numeric(20,6) CHECK (amount_mxn IS NULL OR amount_mxn >= 0),
    cfdi_type truelock.cfdi_type NOT NULL,
    payment_form text,
    payment_method text,
    expedition_place text,
    export_code text,
    cfdi_status truelock.cfdi_status NOT NULL DEFAULT 'NOT_CHECKED',
    cancelled_at timestamptz,
    cancellation_reason text,
    replacement_uuid text,
    status_checked_at timestamptz,
    raw_xml_sha256 text CHECK (raw_xml_sha256 IS NULL OR truelock.is_sha256(raw_xml_sha256)),
    parse_warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT invoices_source_locator_uq UNIQUE (source_file_id, source_locator),
    CONSTRAINT invoices_parse_warnings_array CHECK (jsonb_typeof(parse_warnings) = 'array'),
    CONSTRAINT invoices_payload_object CHECK (jsonb_typeof(raw_payload) = 'object'),
    CONSTRAINT invoices_cancelled_timestamp CHECK (
        cfdi_status <> 'CANCELLED' OR cancelled_at IS NOT NULL
    )
);

-- UUID is deliberately indexed, not unique. Repeated UUIDs must remain visible to
-- duplicate-import and duplicate-invoice detectors instead of being silently dropped.
CREATE INDEX invoices_case_uuid_idx ON truelock.invoices (case_id, uuid);
CREATE INDEX invoices_case_issuer_date_idx
    ON truelock.invoices (case_id, rfc_issuer, issue_timestamp);
CREATE INDEX invoices_case_receiver_date_idx
    ON truelock.invoices (case_id, rfc_receiver, issue_timestamp);
CREATE INDEX invoices_case_total_idx
    ON truelock.invoices (case_id, currency, total);

CREATE TABLE truelock.invoice_concepts (
    invoice_concept_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id uuid NOT NULL REFERENCES truelock.invoices(invoice_id) ON DELETE CASCADE,
    line_no integer NOT NULL CHECK (line_no > 0),
    product_service_code text,
    identification_no text,
    quantity numeric(20,6) NOT NULL CHECK (quantity >= 0),
    unit_code text,
    unit_name text,
    description text NOT NULL,
    unit_value numeric(20,6) NOT NULL CHECK (unit_value >= 0),
    amount numeric(20,6) NOT NULL CHECK (amount >= 0),
    discount numeric(20,6) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    tax_object_code text,
    tax_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT invoice_concepts_line_uq UNIQUE (invoice_id, line_no),
    CONSTRAINT invoice_concepts_tax_object CHECK (jsonb_typeof(tax_json) = 'object'),
    CONSTRAINT invoice_concepts_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE TABLE truelock.invoice_relationships (
    invoice_relationship_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id uuid NOT NULL REFERENCES truelock.invoices(invoice_id) ON DELETE CASCADE,
    relationship_type text NOT NULL,
    related_uuid text NOT NULL,
    related_invoice_id uuid REFERENCES truelock.invoices(invoice_id),
    source_locator text,
    CONSTRAINT invoice_relationship_identity_uq UNIQUE (
        invoice_id, relationship_type, related_uuid
    )
);

CREATE INDEX invoice_relationships_related_uuid_idx
    ON truelock.invoice_relationships (related_uuid);

CREATE TABLE truelock.payment_complements (
    payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id),
    source_locator text NOT NULL,
    payment_cfdi_uuid text,
    payment_date timestamptz NOT NULL,
    currency char(3) NOT NULL,
    exchange_rate numeric(20,10) CHECK (exchange_rate IS NULL OR exchange_rate > 0),
    payment_form text,
    payment_amount numeric(20,6) NOT NULL CHECK (payment_amount >= 0),
    amount_mxn numeric(20,6) CHECK (amount_mxn IS NULL OR amount_mxn >= 0),
    operation_number text,
    origin_account_text text,
    beneficiary_account_text text,
    origin_bank_account_id uuid REFERENCES truelock.bank_accounts(bank_account_id),
    beneficiary_bank_account_id uuid REFERENCES truelock.bank_accounts(bank_account_id),
    record_sha256 text CHECK (record_sha256 IS NULL OR truelock.is_sha256(record_sha256)),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT payment_complements_source_locator_uq UNIQUE (source_file_id, source_locator),
    CONSTRAINT payment_complements_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE INDEX payment_complements_case_date_idx
    ON truelock.payment_complements (case_id, payment_date);
CREATE INDEX payment_complements_uuid_idx
    ON truelock.payment_complements (payment_cfdi_uuid);

CREATE TABLE truelock.payment_documents (
    payment_document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id uuid NOT NULL REFERENCES truelock.payment_complements(payment_id) ON DELETE CASCADE,
    invoice_id uuid REFERENCES truelock.invoices(invoice_id),
    related_document_uuid text NOT NULL,
    document_currency char(3) NOT NULL,
    equivalence numeric(20,10) CHECK (equivalence IS NULL OR equivalence > 0),
    installment_no integer CHECK (installment_no IS NULL OR installment_no > 0),
    previous_balance numeric(20,6) CHECK (previous_balance IS NULL OR previous_balance >= 0),
    amount_paid numeric(20,6) NOT NULL CHECK (amount_paid >= 0),
    remaining_balance numeric(20,6) CHECK (remaining_balance IS NULL OR remaining_balance >= 0),
    tax_object_code text,
    tax_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_locator text,
    CONSTRAINT payment_documents_payment_uuid_installment_uq UNIQUE (
        payment_id, related_document_uuid, installment_no
    ),
    CONSTRAINT payment_documents_balance_math CHECK (
        previous_balance IS NULL OR remaining_balance IS NULL OR
        abs(previous_balance - amount_paid - remaining_balance) <= 0.02
    ),
    CONSTRAINT payment_documents_tax_object CHECK (jsonb_typeof(tax_json) = 'object')
);

CREATE INDEX payment_documents_related_uuid_idx
    ON truelock.payment_documents (related_document_uuid);
CREATE INDEX payment_documents_invoice_idx ON truelock.payment_documents (invoice_id);

CREATE TABLE truelock.bank_transactions (
    bank_transaction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id),
    source_locator text NOT NULL,
    external_transaction_id text,
    observed_bank_account_id uuid REFERENCES truelock.bank_accounts(bank_account_id),
    booked_at timestamptz NOT NULL,
    value_date date,
    direction truelock.cash_direction NOT NULL,
    origin_bank_account_id uuid REFERENCES truelock.bank_accounts(bank_account_id),
    destination_bank_account_id uuid REFERENCES truelock.bank_accounts(bank_account_id),
    origin_entity_id uuid REFERENCES truelock.entities(entity_id),
    destination_entity_id uuid REFERENCES truelock.entities(entity_id),
    amount numeric(20,6) NOT NULL CHECK (amount > 0),
    currency char(3) NOT NULL,
    exchange_rate numeric(20,10) CHECK (exchange_rate IS NULL OR exchange_rate > 0),
    amount_mxn numeric(20,6) CHECK (amount_mxn IS NULL OR amount_mxn > 0),
    reference text,
    concept text,
    transaction_type text,
    counterparty_name text,
    counterparty_rfc text,
    balance_after numeric(20,6),
    is_reversal boolean NOT NULL DEFAULT false,
    reverses_transaction_id uuid REFERENCES truelock.bank_transactions(bank_transaction_id),
    record_sha256 text CHECK (record_sha256 IS NULL OR truelock.is_sha256(record_sha256)),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT bank_transactions_source_locator_uq UNIQUE (source_file_id, source_locator),
    CONSTRAINT bank_transactions_accounts_distinct CHECK (
        origin_bank_account_id IS NULL OR destination_bank_account_id IS NULL OR
        origin_bank_account_id <> destination_bank_account_id
    ),
    CONSTRAINT bank_transactions_reversal_target CHECK (
        NOT is_reversal OR reverses_transaction_id IS NOT NULL
    ),
    CONSTRAINT bank_transactions_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE INDEX bank_transactions_case_booked_idx
    ON truelock.bank_transactions (case_id, booked_at);
CREATE INDEX bank_transactions_origin_time_idx
    ON truelock.bank_transactions (case_id, origin_bank_account_id, booked_at);
CREATE INDEX bank_transactions_destination_time_idx
    ON truelock.bank_transactions (case_id, destination_bank_account_id, booked_at);
CREATE INDEX bank_transactions_origin_entity_time_idx
    ON truelock.bank_transactions (case_id, origin_entity_id, booked_at);
CREATE INDEX bank_transactions_destination_entity_time_idx
    ON truelock.bank_transactions (case_id, destination_entity_id, booked_at);
CREATE INDEX bank_transactions_external_id_idx
    ON truelock.bank_transactions (case_id, external_transaction_id);

CREATE TABLE truelock.ledger_entries (
    journal_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id),
    source_locator text NOT NULL,
    external_journal_line_id text,
    journal_entry_id text NOT NULL,
    posting_date date NOT NULL,
    account_code text NOT NULL,
    account_name text,
    account_type text,
    debit numeric(20,6) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit numeric(20,6) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    currency char(3) NOT NULL,
    base_amount_mxn numeric(20,6),
    entity_id uuid REFERENCES truelock.entities(entity_id),
    supplier_id uuid REFERENCES truelock.suppliers(supplier_id),
    customer_entity_id uuid REFERENCES truelock.entities(entity_id),
    invoice_id uuid REFERENCES truelock.invoices(invoice_id),
    invoice_uuid text,
    document_reference text,
    cost_center text,
    purchase_order text,
    description text,
    record_sha256 text CHECK (record_sha256 IS NULL OR truelock.is_sha256(record_sha256)),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ledger_entries_source_locator_uq UNIQUE (source_file_id, source_locator),
    CONSTRAINT ledger_entries_one_sided CHECK (
        (debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)
    ),
    CONSTRAINT ledger_entries_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE INDEX ledger_entries_case_journal_idx
    ON truelock.ledger_entries (case_id, journal_entry_id);
CREATE INDEX ledger_entries_case_posting_idx
    ON truelock.ledger_entries (case_id, posting_date);
CREATE INDEX ledger_entries_invoice_id_idx ON truelock.ledger_entries (invoice_id);
CREATE INDEX ledger_entries_invoice_uuid_idx ON truelock.ledger_entries (invoice_uuid);
CREATE INDEX ledger_entries_supplier_idx ON truelock.ledger_entries (supplier_id, posting_date);

INSERT INTO truelock.schema_migrations(version) VALUES ('0004_canonical_financial_records');
