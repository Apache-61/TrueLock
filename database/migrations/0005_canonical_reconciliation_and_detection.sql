CREATE TYPE truelock.confidence_label AS ENUM ('LOW', 'MEDIUM', 'HIGH');
CREATE TYPE truelock.reconciliation_status AS ENUM (
    'CANDIDATE', 'CONFIRMED', 'REJECTED', 'SUPERSEDED'
);
CREATE TYPE truelock.knowledge_state AS ENUM (
    'KNOWN', 'UNKNOWN', 'MISSING', 'NOT_APPLICABLE', 'NOT_FOUND'
);
CREATE TYPE truelock.record_type AS ENUM (
    'SOURCE_FILE', 'SUPPLIER', 'INVOICE', 'INVOICE_CONCEPT',
    'PAYMENT_COMPLEMENT', 'PAYMENT_DOCUMENT', 'BANK_TRANSACTION',
    'LEDGER_ENTRY', 'ENTITY', 'ENTITY_RELATIONSHIP', 'SAT_69B_RECORD',
    'RECONCILIATION_MATCH', 'DETECTOR_RUN', 'ANOMALY', 'LEAD',
    'INVESTIGATION_STEP', 'EXPOSURE_CALCULATION', 'OTHER'
);
CREATE TYPE truelock.anomaly_status AS ENUM (
    'OPEN', 'GROUPED_INTO_LEAD', 'DISMISSED', 'RESOLVED'
);
CREATE TYPE truelock.lead_status AS ENUM (
    'OPEN', 'INVESTIGATING', 'SUPPORTED', 'REJECTED',
    'INSUFFICIENT_EVIDENCE', 'CLOSED'
);
CREATE TYPE truelock.priority_label AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

CREATE TABLE truelock.reconciliation_matches (
    reconciliation_match_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    match_type text NOT NULL,
    status truelock.reconciliation_status NOT NULL DEFAULT 'CANDIDATE',
    confidence truelock.confidence_label NOT NULL,
    matched_amount numeric(20,6) NOT NULL CHECK (matched_amount >= 0),
    currency char(3) NOT NULL,
    amount_mxn numeric(20,6) CHECK (amount_mxn IS NULL OR amount_mxn >= 0),
    unmatched_amount numeric(20,6) NOT NULL DEFAULT 0 CHECK (unmatched_amount >= 0),
    tolerance_used numeric(20,6) NOT NULL DEFAULT 0 CHECK (tolerance_used >= 0),
    rules jsonb NOT NULL DEFAULT '[]'::jsonb,
    explanation text NOT NULL,
    coverage_state truelock.knowledge_state NOT NULL DEFAULT 'KNOWN',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT reconciliation_rules_array CHECK (jsonb_typeof(rules) = 'array')
);

CREATE TABLE truelock.reconciliation_invoice_allocations (
    reconciliation_match_id uuid NOT NULL
        REFERENCES truelock.reconciliation_matches(reconciliation_match_id) ON DELETE CASCADE,
    invoice_id uuid NOT NULL REFERENCES truelock.invoices(invoice_id) ON DELETE CASCADE,
    allocated_amount numeric(20,6) NOT NULL CHECK (allocated_amount >= 0),
    PRIMARY KEY (reconciliation_match_id, invoice_id)
);

CREATE TABLE truelock.reconciliation_bank_allocations (
    reconciliation_match_id uuid NOT NULL
        REFERENCES truelock.reconciliation_matches(reconciliation_match_id) ON DELETE CASCADE,
    bank_transaction_id uuid NOT NULL
        REFERENCES truelock.bank_transactions(bank_transaction_id) ON DELETE CASCADE,
    allocated_amount numeric(20,6) NOT NULL CHECK (allocated_amount >= 0),
    PRIMARY KEY (reconciliation_match_id, bank_transaction_id)
);

CREATE TABLE truelock.reconciliation_payment_document_links (
    reconciliation_match_id uuid NOT NULL
        REFERENCES truelock.reconciliation_matches(reconciliation_match_id) ON DELETE CASCADE,
    payment_document_id uuid NOT NULL
        REFERENCES truelock.payment_documents(payment_document_id) ON DELETE CASCADE,
    PRIMARY KEY (reconciliation_match_id, payment_document_id)
);

CREATE TABLE truelock.reconciliation_ledger_links (
    reconciliation_match_id uuid NOT NULL
        REFERENCES truelock.reconciliation_matches(reconciliation_match_id) ON DELETE CASCADE,
    journal_line_id uuid NOT NULL REFERENCES truelock.ledger_entries(journal_line_id) ON DELETE CASCADE,
    PRIMARY KEY (reconciliation_match_id, journal_line_id)
);

CREATE INDEX reconciliation_matches_case_status_idx
    ON truelock.reconciliation_matches (case_id, status, match_type);

CREATE TABLE truelock.detector_runs (
    detector_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    detector_code text NOT NULL,
    detector_version text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'RUNNING',
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    records_scanned bigint NOT NULL DEFAULT 0 CHECK (records_scanned >= 0),
    anomalies_emitted integer NOT NULL DEFAULT 0 CHECK (anomalies_emitted >= 0),
    error_details jsonb NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT detector_runs_parameters_object CHECK (jsonb_typeof(parameters) = 'object'),
    CONSTRAINT detector_runs_errors_array CHECK (jsonb_typeof(error_details) = 'array'),
    CONSTRAINT detector_runs_time_order CHECK (
        finished_at IS NULL OR finished_at >= started_at
    )
);

CREATE TABLE truelock.anomalies (
    anomaly_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    detector_run_id uuid NOT NULL REFERENCES truelock.detector_runs(detector_run_id),
    detector_code text NOT NULL,
    status truelock.anomaly_status NOT NULL DEFAULT 'OPEN',
    title text NOT NULL,
    description text NOT NULL,
    strength numeric(5,4) NOT NULL CHECK (strength BETWEEN 0 AND 1),
    amount_mxn numeric(20,6) CHECK (amount_mxn IS NULL OR amount_mxn >= 0),
    occurred_at timestamptz,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT anomalies_details_object CHECK (jsonb_typeof(details) = 'object')
);

CREATE TABLE truelock.anomaly_records (
    anomaly_id uuid NOT NULL REFERENCES truelock.anomalies(anomaly_id) ON DELETE CASCADE,
    record_type truelock.record_type NOT NULL,
    record_id uuid NOT NULL,
    role text NOT NULL DEFAULT 'SOURCE',
    source_file_id uuid REFERENCES truelock.source_files(source_file_id),
    source_locator text,
    PRIMARY KEY (anomaly_id, record_type, record_id, role)
);

CREATE INDEX anomalies_case_detector_idx
    ON truelock.anomalies (case_id, detector_code, status);
CREATE INDEX anomaly_records_lookup_idx
    ON truelock.anomaly_records (record_type, record_id);

CREATE TABLE truelock.leads (
    lead_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    display_id text NOT NULL,
    title text NOT NULL,
    risk_score numeric(5,2) NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_score_version text NOT NULL,
    priority truelock.priority_label NOT NULL,
    status truelock.lead_status NOT NULL DEFAULT 'OPEN',
    reason_summary text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT leads_case_display_id_uq UNIQUE (case_id, display_id)
);

CREATE TABLE truelock.lead_anomalies (
    lead_id uuid NOT NULL REFERENCES truelock.leads(lead_id) ON DELETE CASCADE,
    anomaly_id uuid NOT NULL REFERENCES truelock.anomalies(anomaly_id) ON DELETE RESTRICT,
    PRIMARY KEY (lead_id, anomaly_id)
);

CREATE TABLE truelock.lead_entities (
    lead_id uuid NOT NULL REFERENCES truelock.leads(lead_id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE RESTRICT,
    role text NOT NULL DEFAULT 'SUBJECT',
    PRIMARY KEY (lead_id, entity_id, role)
);

CREATE TABLE truelock.risk_score_components (
    risk_component_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id uuid NOT NULL REFERENCES truelock.leads(lead_id) ON DELETE CASCADE,
    component_code text NOT NULL,
    detector_weight numeric(8,4) NOT NULL,
    detector_strength numeric(5,4) NOT NULL CHECK (detector_strength BETWEEN 0 AND 1),
    source_reliability numeric(5,4) NOT NULL CHECK (source_reliability BETWEEN 0 AND 1),
    points numeric(8,4) NOT NULL,
    mitigating boolean NOT NULL DEFAULT false,
    explanation text NOT NULL,
    anomaly_id uuid REFERENCES truelock.anomalies(anomaly_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX leads_case_priority_idx ON truelock.leads (case_id, status, risk_score DESC);

CREATE VIEW truelock.v_invoice_settlement AS
WITH confirmed AS (
    SELECT
        ria.invoice_id,
        sum(ria.allocated_amount) AS allocated_amount
    FROM truelock.reconciliation_invoice_allocations ria
    JOIN truelock.reconciliation_matches rm
      ON rm.reconciliation_match_id = ria.reconciliation_match_id
    WHERE rm.status = 'CONFIRMED'
    GROUP BY ria.invoice_id
)
SELECT
    i.case_id,
    i.invoice_id,
    i.uuid,
    i.cfdi_type,
    i.cfdi_status,
    i.currency,
    i.total AS invoice_amount,
    coalesce(c.allocated_amount, 0) AS settled_amount,
    greatest(i.total - coalesce(c.allocated_amount, 0), 0) AS open_amount,
    greatest(coalesce(c.allocated_amount, 0) - i.total, 0) AS excess_amount,
    CASE
        WHEN i.cfdi_status IN ('CANCELLED', 'SUBSTITUTED') THEN 'NOT_APPLICABLE'
        WHEN coalesce(c.allocated_amount, 0) = 0 THEN 'UNPAID_OR_UNMATCHED'
        WHEN coalesce(c.allocated_amount, 0) < i.total THEN 'PARTIAL'
        WHEN coalesce(c.allocated_amount, 0) = i.total THEN 'SETTLED'
        ELSE 'OVERPAID'
    END AS settlement_status
FROM truelock.invoices i
LEFT JOIN confirmed c ON c.invoice_id = i.invoice_id;

CREATE VIEW truelock.v_bank_graph_edges AS
SELECT
    bt.case_id,
    bt.bank_transaction_id,
    bt.origin_entity_id,
    bt.destination_entity_id,
    bt.origin_bank_account_id,
    bt.destination_bank_account_id,
    bt.amount,
    bt.currency,
    bt.amount_mxn,
    bt.booked_at,
    bt.reference,
    bt.concept,
    bt.is_reversal
FROM truelock.bank_transactions bt
WHERE bt.origin_bank_account_id IS NOT NULL
  AND bt.destination_bank_account_id IS NOT NULL;

CREATE VIEW truelock.v_shared_bank_accounts AS
SELECT
    ba.case_id,
    ba.bank_account_id,
    ba.masked_account,
    count(DISTINCT eba.entity_id) AS entity_count,
    array_agg(DISTINCT eba.entity_id ORDER BY eba.entity_id) AS entity_ids
FROM truelock.bank_accounts ba
JOIN truelock.entity_bank_accounts eba ON eba.bank_account_id = ba.bank_account_id
GROUP BY ba.case_id, ba.bank_account_id, ba.masked_account
HAVING count(DISTINCT eba.entity_id) > 1;

INSERT INTO truelock.schema_migrations(version) VALUES ('0005_canonical_reconciliation_and_detection');
