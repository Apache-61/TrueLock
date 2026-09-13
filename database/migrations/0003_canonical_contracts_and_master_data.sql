CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS truelock;

CREATE TABLE truelock.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TYPE truelock.case_status AS ENUM (
    'CREATED', 'INGESTING', 'READY', 'INVESTIGATING', 'COMPLETED', 'FAILED'
);

CREATE TYPE truelock.ingestion_status AS ENUM (
    'RECEIVED', 'PARSING', 'IMPORTED', 'PARTIAL', 'REJECTED'
);

CREATE TYPE truelock.dataset_kind AS ENUM (
    'SUPPLIER_MASTER', 'CFDI_INVOICE', 'CFDI_PAYMENT', 'BANK', 'LEDGER',
    'SAT_69B', 'ENTITY_RELATIONSHIP', 'OTHER'
);

CREATE TYPE truelock.entity_type AS ENUM (
    'COMPANY', 'SUPPLIER', 'CUSTOMER', 'PERSON', 'BANK_ACCOUNT', 'UNKNOWN'
);

CREATE TYPE truelock.identifier_type AS ENUM (
    'RFC', 'SUPPLIER_ID', 'CUSTOMER_ID', 'EMPLOYEE_ID', 'NORMALIZED_NAME',
    'BANK_ACCOUNT', 'CLABE', 'EMAIL', 'PHONE', 'OTHER'
);

CREATE TYPE truelock.relationship_type AS ENUM (
    'SAME_LEGAL_ENTITY', 'SHARED_BANK_ACCOUNT', 'SHARED_ADDRESS',
    'SHARED_CONTACT', 'BENEFICIAL_OWNER', 'EMPLOYEE_OF', 'SUBSIDIARY_OF',
    'RELATED_PARTY', 'PAYS', 'OTHER'
);

CREATE TYPE truelock.sat_69b_status AS ENUM (
    'PRESUNTO', 'DEFINITIVO', 'DESVIRTUADO', 'SENTENCIA_FAVORABLE', 'NOT_FOUND'
);

CREATE OR REPLACE FUNCTION truelock.normalize_legal_name(input text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT NULLIF(
        btrim(
            regexp_replace(
                translate(upper(coalesce(input, '')), 'ÁÉÍÓÚÜÑ', 'AEIOUUN'),
                '[^A-Z0-9]+',
                ' ',
                'g'
            )
        ),
        ''
    );
$$;

CREATE OR REPLACE FUNCTION truelock.is_sha256(input text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT input ~ '^[0-9a-f]{64}$';
$$;

CREATE TABLE truelock.organizations (
    organization_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name text NOT NULL,
    rfc text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT organizations_rfc_format CHECK (
        rfc IS NULL OR rfc ~ '^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$'
    )
);

CREATE UNIQUE INDEX organizations_rfc_uq
    ON truelock.organizations (rfc)
    WHERE rfc IS NOT NULL;

CREATE TABLE truelock.cases (
    case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES truelock.organizations(organization_id),
    display_id text NOT NULL,
    title text NOT NULL,
    status truelock.case_status NOT NULL DEFAULT 'CREATED',
    base_currency char(3) NOT NULL DEFAULT 'MXN',
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    closed_at timestamptz,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT cases_display_id_uq UNIQUE (organization_id, display_id),
    CONSTRAINT cases_closed_after_open CHECK (closed_at IS NULL OR closed_at >= opened_at),
    CONSTRAINT cases_limitations_array CHECK (jsonb_typeof(limitations) = 'array'),
    CONSTRAINT cases_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE truelock.source_files (
    source_file_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    original_filename text NOT NULL,
    dataset_kind truelock.dataset_kind NOT NULL,
    media_type text,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    sha256 text NOT NULL CHECK (truelock.is_sha256(sha256)),
    parser_name text,
    parser_version text,
    status truelock.ingestion_status NOT NULL DEFAULT 'RECEIVED',
    record_count integer NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    rejected_count integer NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    ingested_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT source_files_case_hash_uq UNIQUE (case_id, sha256),
    CONSTRAINT source_files_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE truelock.case_source_files (
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id) ON DELETE CASCADE,
    PRIMARY KEY (case_id, source_file_id)
);

CREATE TABLE truelock.data_coverage (
    coverage_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    dataset_kind truelock.dataset_kind NOT NULL,
    covered_from timestamptz,
    covered_to timestamptz,
    is_complete boolean,
    completeness_reason text,
    timezone_name text,
    sign_convention text,
    assessed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT data_coverage_range CHECK (
        covered_to IS NULL OR covered_from IS NULL OR covered_to >= covered_from
    ),
    CONSTRAINT data_coverage_sign_convention CHECK (
        sign_convention IS NULL OR sign_convention IN (
            'POSITIVE_IS_INFLOW', 'POSITIVE_IS_OUTFLOW', 'SEPARATE_DIRECTION', 'UNKNOWN'
        )
    )
);

CREATE TABLE truelock.ingest_rejections (
    rejection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id) ON DELETE CASCADE,
    source_locator text NOT NULL,
    error_code text NOT NULL,
    error_message text NOT NULL,
    raw_payload jsonb,
    rejected_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ingest_rejections_payload_shape CHECK (
        raw_payload IS NULL OR jsonb_typeof(raw_payload) IN ('object', 'array', 'string')
    )
);

CREATE TABLE truelock.entities (
    entity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    entity_type truelock.entity_type NOT NULL,
    canonical_name text NOT NULL,
    normalized_name text GENERATED ALWAYS AS (truelock.normalize_legal_name(canonical_name)) STORED,
    legal_name text,
    trade_name text,
    rfc text,
    status text NOT NULL DEFAULT 'ACTIVE',
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    source_locator text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT entities_rfc_format CHECK (
        rfc IS NULL OR rfc ~ '^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$'
    ),
    CONSTRAINT entities_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE UNIQUE INDEX entities_case_rfc_uq
    ON truelock.entities (case_id, rfc)
    WHERE rfc IS NOT NULL;

CREATE TABLE truelock.entity_identifiers (
    entity_identifier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE CASCADE,
    identifier_type truelock.identifier_type NOT NULL,
    identifier_value text NOT NULL,
    normalized_value text NOT NULL,
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    source_locator text,
    confidence numeric(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    is_merge_key boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT entity_identifiers_case_value_uq UNIQUE (
        case_id, entity_id, identifier_type, normalized_value
    )
);

CREATE INDEX entity_identifiers_lookup_idx
    ON truelock.entity_identifiers (case_id, identifier_type, normalized_value);

CREATE TABLE truelock.entity_relationships (
    relationship_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    entity_a_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE CASCADE,
    entity_b_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE CASCADE,
    relationship_type truelock.relationship_type NOT NULL,
    relationship_value text,
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    auto_merge boolean NOT NULL DEFAULT false,
    basis jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    source_locator text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT entity_relationship_distinct CHECK (entity_a_id <> entity_b_id),
    CONSTRAINT entity_relationship_basis_array CHECK (jsonb_typeof(basis) = 'array'),
    CONSTRAINT entity_relationship_no_unsafe_merge CHECK (
        NOT auto_merge OR relationship_type = 'SAME_LEGAL_ENTITY'
    )
);

CREATE UNIQUE INDEX entity_relationship_identity_uq
    ON truelock.entity_relationships (
        case_id,
        LEAST(entity_a_id, entity_b_id),
        GREATEST(entity_a_id, entity_b_id),
        relationship_type,
        coalesce(relationship_value, '')
    );

CREATE TABLE truelock.bank_accounts (
    bank_account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    account_fingerprint text NOT NULL CHECK (truelock.is_sha256(account_fingerprint)),
    account_number text,
    clabe text,
    masked_account text NOT NULL,
    bank_name text,
    currency char(3),
    country_code char(2) NOT NULL DEFAULT 'MX',
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT bank_accounts_case_fingerprint_uq UNIQUE (case_id, account_fingerprint),
    CONSTRAINT bank_accounts_identifier_present CHECK (
        account_number IS NOT NULL OR clabe IS NOT NULL
    ),
    CONSTRAINT bank_accounts_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE TABLE truelock.entity_bank_accounts (
    entity_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE CASCADE,
    bank_account_id uuid NOT NULL REFERENCES truelock.bank_accounts(bank_account_id) ON DELETE CASCADE,
    is_primary boolean NOT NULL DEFAULT false,
    valid_from date,
    valid_to date,
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    source_locator text,
    PRIMARY KEY (entity_id, bank_account_id),
    CONSTRAINT entity_bank_accounts_dates CHECK (
        valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from
    )
);

CREATE TABLE truelock.suppliers (
    supplier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE RESTRICT,
    external_supplier_id text NOT NULL,
    legal_name text NOT NULL,
    trade_name text,
    rfc text,
    address_raw text,
    address_normalized text,
    created_at_source timestamptz,
    status text NOT NULL DEFAULT 'ACTIVE',
    category text,
    business_activity text,
    contact_name text,
    email text,
    phone text,
    beneficiary_name text,
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id),
    source_locator text NOT NULL,
    record_sha256 text CHECK (record_sha256 IS NULL OR truelock.is_sha256(record_sha256)),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT suppliers_case_external_id_uq UNIQUE (case_id, external_supplier_id),
    CONSTRAINT suppliers_source_locator_uq UNIQUE (source_file_id, source_locator),
    CONSTRAINT suppliers_payload_object CHECK (jsonb_typeof(raw_payload) = 'object')
);

CREATE TABLE truelock.sat_69b_snapshots (
    sat_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file_id uuid NOT NULL REFERENCES truelock.source_files(source_file_id),
    snapshot_date date NOT NULL,
    retrieved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    source_url text,
    publication_reference text,
    notes text,
    CONSTRAINT sat_snapshot_source_date_uq UNIQUE (source_file_id, snapshot_date)
);

CREATE TABLE truelock.sat_69b_records (
    sat_record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sat_snapshot_id uuid NOT NULL REFERENCES truelock.sat_69b_snapshots(sat_snapshot_id) ON DELETE CASCADE,
    rfc text NOT NULL,
    legal_name text,
    status truelock.sat_69b_status NOT NULL,
    source_publication_date date,
    source_office_reference text,
    raw_status_text text,
    source_locator text NOT NULL,
    raw_row_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT sat_69b_record_identity_uq UNIQUE (
        sat_snapshot_id, rfc, status, source_locator
    ),
    CONSTRAINT sat_69b_records_payload_object CHECK (jsonb_typeof(raw_row_json) = 'object')
);

CREATE INDEX sat_69b_records_rfc_idx ON truelock.sat_69b_records (rfc, status);
CREATE INDEX source_files_case_kind_idx ON truelock.source_files (case_id, dataset_kind);
CREATE INDEX entities_case_name_idx ON truelock.entities (case_id, normalized_name);
CREATE INDEX entity_relationships_a_idx ON truelock.entity_relationships (case_id, entity_a_id);
CREATE INDEX entity_relationships_b_idx ON truelock.entity_relationships (case_id, entity_b_id);
CREATE INDEX suppliers_case_rfc_idx ON truelock.suppliers (case_id, rfc);

INSERT INTO truelock.schema_migrations(version) VALUES ('0003_canonical_contracts_and_master_data');
