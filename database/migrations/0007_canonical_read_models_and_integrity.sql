CREATE TABLE truelock.case_file_versions (
    case_file_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE RESTRICT,
    version_no integer NOT NULL CHECK (version_no > 0),
    case_file jsonb NOT NULL,
    case_file_sha256 text GENERATED ALWAYS AS (
        encode(digest(case_file::text, 'sha256'), 'hex')
    ) STORED,
    previous_version_id uuid REFERENCES truelock.case_file_versions(case_file_version_id),
    solana_cluster text,
    solana_signature text,
    anchored_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT case_file_versions_case_version_uq UNIQUE (case_id, version_no),
    CONSTRAINT case_file_versions_object CHECK (jsonb_typeof(case_file) = 'object'),
    CONSTRAINT case_file_versions_chain CHECK (
        (version_no = 1 AND previous_version_id IS NULL) OR
        (version_no > 1 AND previous_version_id IS NOT NULL)
    ),
    CONSTRAINT case_file_versions_solana_fields CHECK (
        solana_signature IS NULL OR (solana_cluster IS NOT NULL AND anchored_at IS NOT NULL)
    )
);

CREATE TABLE truelock.operational_events (
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    event_id uuid NOT NULL DEFAULT gen_random_uuid(),
    case_id uuid REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    event_type text NOT NULL,
    duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (occurred_at, event_id),
    CONSTRAINT operational_events_attributes_object CHECK (jsonb_typeof(attributes) = 'object')
);

CREATE INDEX operational_events_case_time_idx
    ON truelock.operational_events (case_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION truelock.ensure_source_file_case_match()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_file_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM truelock.source_files sf
        WHERE sf.source_file_id = NEW.source_file_id
          AND sf.case_id = NEW.case_id
    ) THEN
        RAISE EXCEPTION 'source_file_id % does not belong to case_id %',
            NEW.source_file_id, NEW.case_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER entities_source_case_guard
BEFORE INSERT OR UPDATE OF case_id, source_file_id ON truelock.entities
FOR EACH ROW EXECUTE FUNCTION truelock.ensure_source_file_case_match();

CREATE TRIGGER suppliers_source_case_guard
BEFORE INSERT OR UPDATE OF case_id, source_file_id ON truelock.suppliers
FOR EACH ROW EXECUTE FUNCTION truelock.ensure_source_file_case_match();

CREATE TRIGGER invoices_source_case_guard
BEFORE INSERT OR UPDATE OF case_id, source_file_id ON truelock.invoices
FOR EACH ROW EXECUTE FUNCTION truelock.ensure_source_file_case_match();

CREATE TRIGGER payment_complements_source_case_guard
BEFORE INSERT OR UPDATE OF case_id, source_file_id ON truelock.payment_complements
FOR EACH ROW EXECUTE FUNCTION truelock.ensure_source_file_case_match();

CREATE TRIGGER bank_transactions_source_case_guard
BEFORE INSERT OR UPDATE OF case_id, source_file_id ON truelock.bank_transactions
FOR EACH ROW EXECUTE FUNCTION truelock.ensure_source_file_case_match();

CREATE TRIGGER ledger_entries_source_case_guard
BEFORE INSERT OR UPDATE OF case_id, source_file_id ON truelock.ledger_entries
FOR EACH ROW EXECUTE FUNCTION truelock.ensure_source_file_case_match();

CREATE OR REPLACE FUNCTION truelock.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER leads_touch_updated_at
BEFORE UPDATE ON truelock.leads
FOR EACH ROW EXECUTE FUNCTION truelock.touch_updated_at();

CREATE TRIGGER case_file_versions_append_only
BEFORE UPDATE OR DELETE ON truelock.case_file_versions
FOR EACH ROW EXECUTE FUNCTION truelock.prevent_audit_record_mutation();

CREATE OR REPLACE FUNCTION truelock.has_complete_coverage(
    target_case_id uuid,
    target_dataset_kind truelock.dataset_kind,
    required_from timestamptz,
    required_to timestamptz
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM truelock.data_coverage dc
        WHERE dc.case_id = target_case_id
          AND dc.dataset_kind = target_dataset_kind
          AND dc.is_complete IS TRUE
          AND (required_from IS NULL OR dc.covered_from IS NULL OR dc.covered_from <= required_from)
          AND (required_to IS NULL OR dc.covered_to IS NULL OR dc.covered_to >= required_to)
    );
$$;

CREATE OR REPLACE FUNCTION truelock.trace_bank_paths(
    target_case_id uuid,
    start_transaction_id uuid,
    max_depth integer DEFAULT 4,
    max_horizon interval DEFAULT interval '30 days'
)
RETURNS TABLE (
    depth integer,
    bank_transaction_id uuid,
    origin_bank_account_id uuid,
    destination_bank_account_id uuid,
    booked_at timestamptz,
    edge_amount_mxn numeric,
    path_traced_cap_mxn numeric,
    transaction_path uuid[]
)
LANGUAGE sql
STABLE
AS $$
WITH RECURSIVE trace AS (
    SELECT
        1 AS depth,
        bt.bank_transaction_id,
        bt.origin_bank_account_id,
        bt.destination_bank_account_id,
        bt.booked_at,
        coalesce(bt.amount_mxn, CASE WHEN bt.currency = 'MXN' THEN bt.amount END) AS edge_amount_mxn,
        coalesce(bt.amount_mxn, CASE WHEN bt.currency = 'MXN' THEN bt.amount END) AS path_traced_cap_mxn,
        ARRAY[bt.bank_transaction_id]::uuid[] AS transaction_path,
        bt.booked_at AS root_time
    FROM truelock.bank_transactions bt
    WHERE bt.case_id = target_case_id
      AND bt.bank_transaction_id = start_transaction_id
      AND NOT bt.is_reversal

    UNION ALL

    SELECT
        t.depth + 1,
        next_bt.bank_transaction_id,
        next_bt.origin_bank_account_id,
        next_bt.destination_bank_account_id,
        next_bt.booked_at,
        coalesce(next_bt.amount_mxn, CASE WHEN next_bt.currency = 'MXN' THEN next_bt.amount END),
        least(
            t.path_traced_cap_mxn,
            coalesce(next_bt.amount_mxn, CASE WHEN next_bt.currency = 'MXN' THEN next_bt.amount END)
        ),
        t.transaction_path || next_bt.bank_transaction_id,
        t.root_time
    FROM trace t
    JOIN truelock.bank_transactions next_bt
      ON next_bt.case_id = target_case_id
     AND next_bt.origin_bank_account_id = t.destination_bank_account_id
     AND next_bt.booked_at >= t.booked_at
     AND next_bt.booked_at <= t.root_time + max_horizon
     AND NOT next_bt.is_reversal
    WHERE t.depth < greatest(1, least(max_depth, 5))
      AND NOT next_bt.bank_transaction_id = ANY(t.transaction_path)
      AND t.path_traced_cap_mxn IS NOT NULL
)
SELECT
    trace.depth,
    trace.bank_transaction_id,
    trace.origin_bank_account_id,
    trace.destination_bank_account_id,
    trace.booked_at,
    trace.edge_amount_mxn,
    trace.path_traced_cap_mxn,
    trace.transaction_path
FROM trace
ORDER BY trace.depth, trace.booked_at, trace.bank_transaction_id;
$$;

CREATE VIEW truelock.v_latest_sat_69b AS
SELECT DISTINCT ON (sf.case_id, sr.rfc)
    sf.case_id,
    sr.rfc,
    sr.legal_name,
    sr.status,
    ss.snapshot_date,
    ss.retrieved_at,
    ss.publication_reference,
    sr.sat_record_id,
    ss.source_file_id,
    sr.source_locator
FROM truelock.sat_69b_records sr
JOIN truelock.sat_69b_snapshots ss ON ss.sat_snapshot_id = sr.sat_snapshot_id
JOIN truelock.source_files sf ON sf.source_file_id = ss.source_file_id
ORDER BY sf.case_id, sr.rfc, ss.snapshot_date DESC, ss.retrieved_at DESC;

CREATE VIEW truelock.v_ledger_entry_balance AS
SELECT
    case_id,
    journal_entry_id,
    min(posting_date) AS posting_date,
    sum(debit) AS total_debit,
    sum(credit) AS total_credit,
    sum(debit) - sum(credit) AS imbalance,
    abs(sum(debit) - sum(credit)) <= 0.02 AS is_balanced
FROM truelock.ledger_entries
GROUP BY case_id, journal_entry_id;

CREATE VIEW truelock.v_case_ingestion AS
SELECT
    c.case_id,
    c.display_id AS case_display_id,
    sf.dataset_kind,
    count(sf.source_file_id) AS file_count,
    sum(sf.record_count) AS imported_records,
    sum(sf.rejected_count) AS rejected_records,
    bool_and(sf.status = 'IMPORTED') AS all_files_imported,
    bool_or(dc.is_complete IS TRUE) AS has_complete_coverage,
    min(dc.covered_from) AS covered_from,
    max(dc.covered_to) AS covered_to
FROM truelock.cases c
LEFT JOIN truelock.source_files sf ON sf.case_id = c.case_id
LEFT JOIN truelock.data_coverage dc
  ON dc.case_id = c.case_id AND dc.dataset_kind = sf.dataset_kind
GROUP BY c.case_id, c.display_id, sf.dataset_kind;

CREATE VIEW truelock.v_investigation_timeline AS
SELECT
    s.case_id,
    s.investigation_id,
    s.thread_id,
    s.step_id,
    s.sequence,
    s.action,
    s.tool_name,
    s.reason_summary,
    s.tool_inputs,
    s.result_summary,
    s.provenance,
    s.errors,
    s.decision,
    s.started_at,
    s.completed_at,
    s.duration_ms,
    coalesce(array_agg(DISTINCT ie.evidence_id)
        FILTER (WHERE ie.evidence_id IS NOT NULL), ARRAY[]::uuid[]) AS input_evidence_ids,
    coalesce(array_agg(DISTINCT re.evidence_id)
        FILTER (WHERE re.evidence_id IS NOT NULL), ARRAY[]::uuid[]) AS result_evidence_ids
FROM truelock.investigation_steps s
LEFT JOIN truelock.investigation_step_input_evidence ie ON ie.step_id = s.step_id
LEFT JOIN truelock.investigation_step_result_evidence re ON re.step_id = s.step_id
GROUP BY s.case_id, s.investigation_id, s.thread_id, s.step_id, s.sequence,
         s.action, s.tool_name, s.reason_summary, s.tool_inputs, s.result_summary,
         s.provenance, s.errors, s.decision,
         s.started_at, s.completed_at, s.duration_ms;

CREATE VIEW truelock.v_money_trail AS
SELECT
    ec.case_id,
    ec.exposure_calculation_id,
    c.root_flow_id,
    c.component_type,
    c.path_sequence,
    c.source_record_id AS bank_transaction_id,
    bt.origin_entity_id,
    bt.destination_entity_id,
    bt.origin_bank_account_id,
    bt.destination_bank_account_id,
    c.amount_mxn AS traced_amount_mxn,
    bt.booked_at,
    bt.reference,
    bt.concept,
    c.is_supported
FROM truelock.exposure_components c
JOIN truelock.exposure_calculations ec
  ON ec.exposure_calculation_id = c.exposure_calculation_id
JOIN truelock.bank_transactions bt
  ON bt.bank_transaction_id = c.source_record_id
WHERE c.source_record_type = 'BANK_TRANSACTION';

CREATE VIEW truelock.v_case_findings AS
SELECT
    f.case_id,
    f.finding_id,
    f.display_id,
    f.scheme_code,
    f.claim,
    f.status,
    f.confidence_label,
    f.supported_exposure_mxn,
    es.downstream_traced_mxn,
    es.returned_or_recovered_mxn,
    es.credits_mxn,
    es.net_supported_exposure_mxn,
    f.limitations,
    count(DISTINCT fe.evidence_id) AS evidence_count
FROM truelock.findings f
LEFT JOIN truelock.v_exposure_summary es
  ON es.exposure_calculation_id = f.exposure_calculation_id
LEFT JOIN truelock.finding_evidence fe ON fe.finding_id = f.finding_id
GROUP BY f.case_id, f.finding_id, f.display_id, f.scheme_code, f.claim,
         f.status, f.confidence_label, f.supported_exposure_mxn,
         es.downstream_traced_mxn, es.returned_or_recovered_mxn,
         es.credits_mxn, es.net_supported_exposure_mxn, f.limitations;

CREATE INDEX case_file_versions_case_created_idx
    ON truelock.case_file_versions (case_id, version_no DESC);
CREATE INDEX payment_documents_payment_idx ON truelock.payment_documents (payment_id);
CREATE INDEX reconciliation_invoice_allocations_invoice_idx
    ON truelock.reconciliation_invoice_allocations (invoice_id);
CREATE INDEX reconciliation_bank_allocations_transaction_idx
    ON truelock.reconciliation_bank_allocations (bank_transaction_id);
CREATE INDEX finding_evidence_evidence_idx ON truelock.finding_evidence (evidence_id);
CREATE INDEX thread_evidence_evidence_idx ON truelock.thread_evidence (evidence_id);

INSERT INTO truelock.schema_migrations(version) VALUES ('0007_canonical_read_models_and_integrity');
