CREATE TYPE truelock.investigation_status AS ENUM (
    'OPEN', 'RUNNING', 'COMPLETED', 'STOPPED_BY_BUDGET', 'FAILED'
);
CREATE TYPE truelock.thread_status AS ENUM (
    'FORMING', 'TESTING', 'SUPPORTED', 'REJECTED', 'INSUFFICIENT_EVIDENCE', 'STOPPED'
);
CREATE TYPE truelock.step_decision AS ENUM (
    'CONTINUE', 'SUPPORT', 'REJECT', 'ESCALATE', 'STOP', 'ERROR'
);
CREATE TYPE truelock.evidence_role AS ENUM (
    'SUPPORTING', 'CONTRADICTING', 'CONTEXTUAL', 'MITIGATING'
);
CREATE TYPE truelock.finding_status AS ENUM ('DRAFT', 'SUPPORTED', 'RETRACTED');
CREATE TYPE truelock.exposure_component_type AS ENUM (
    'ROOT', 'DOWNSTREAM', 'RETURNED', 'RECOVERED', 'CREDIT'
);

CREATE TABLE truelock.investigations (
    investigation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    lead_id uuid NOT NULL REFERENCES truelock.leads(lead_id) ON DELETE RESTRICT,
    status truelock.investigation_status NOT NULL DEFAULT 'OPEN',
    model_provider text,
    model_name text,
    max_threads integer NOT NULL DEFAULT 2 CHECK (max_threads BETWEEN 1 AND 10),
    max_tool_calls integer NOT NULL DEFAULT 20 CHECK (max_tool_calls BETWEEN 1 AND 100),
    max_runtime_seconds integer NOT NULL DEFAULT 120 CHECK (max_runtime_seconds BETWEEN 1 AND 3600),
    tool_calls_used integer NOT NULL DEFAULT 0 CHECK (tool_calls_used >= 0),
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT investigations_time_order CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

CREATE TABLE truelock.investigation_threads (
    thread_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id uuid NOT NULL
        REFERENCES truelock.investigations(investigation_id) ON DELETE CASCADE,
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    display_id text NOT NULL,
    scheme_code text NOT NULL,
    hypothesis_claim text NOT NULL,
    status truelock.thread_status NOT NULL DEFAULT 'FORMING',
    missing_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    unresolved_material_contradiction boolean NOT NULL DEFAULT false,
    tool_calls_used integer NOT NULL DEFAULT 0 CHECK (tool_calls_used >= 0),
    last_new_evidence_sequence integer,
    outcome_reason text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    closed_at timestamptz,
    CONSTRAINT investigation_threads_display_uq UNIQUE (investigation_id, display_id),
    CONSTRAINT investigation_threads_missing_array CHECK (jsonb_typeof(missing_evidence) = 'array'),
    CONSTRAINT investigation_threads_time_order CHECK (
        closed_at IS NULL OR closed_at >= created_at
    )
);

CREATE TABLE truelock.evidence (
    evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE RESTRICT,
    evidence_type truelock.record_type NOT NULL,
    record_id uuid NOT NULL,
    source_file_id uuid REFERENCES truelock.source_files(source_file_id) ON DELETE RESTRICT,
    source_locator text,
    source_record_sha256 text CHECK (
        source_record_sha256 IS NULL OR truelock.is_sha256(source_record_sha256)
    ),
    facts jsonb NOT NULL,
    facts_sha256 text GENERATED ALWAYS AS (
        encode(digest(facts::text, 'sha256'), 'hex')
    ) STORED,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT evidence_facts_object CHECK (jsonb_typeof(facts) = 'object'),
    CONSTRAINT evidence_record_identity_uq UNIQUE (
        case_id, evidence_type, record_id, facts_sha256
    )
);

CREATE TABLE truelock.thread_evidence (
    thread_id uuid NOT NULL REFERENCES truelock.investigation_threads(thread_id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES truelock.evidence(evidence_id) ON DELETE RESTRICT,
    role truelock.evidence_role NOT NULL,
    assertion_code text,
    added_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (thread_id, evidence_id, role)
);

CREATE TABLE truelock.investigation_steps (
    step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE RESTRICT,
    investigation_id uuid NOT NULL
        REFERENCES truelock.investigations(investigation_id) ON DELETE CASCADE,
    thread_id uuid NOT NULL
        REFERENCES truelock.investigation_threads(thread_id) ON DELETE CASCADE,
    sequence integer NOT NULL CHECK (sequence > 0),
    action text NOT NULL,
    tool_name text,
    reason_summary text NOT NULL,
    tool_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    decision truelock.step_decision NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    duration_ms integer NOT NULL CHECK (duration_ms >= 0),
    interaction_id text,
    previous_interaction_id text,
    request_hash text CHECK (request_hash IS NULL OR truelock.is_sha256(request_hash)),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT investigation_steps_sequence_uq UNIQUE (thread_id, sequence),
    CONSTRAINT investigation_steps_time_order CHECK (completed_at >= started_at),
    CONSTRAINT investigation_steps_inputs_object CHECK (jsonb_typeof(tool_inputs) = 'object'),
    CONSTRAINT investigation_steps_result_object CHECK (jsonb_typeof(result_summary) = 'object'),
    CONSTRAINT investigation_steps_provenance_object CHECK (jsonb_typeof(provenance) = 'object'),
    CONSTRAINT investigation_steps_errors_array CHECK (jsonb_typeof(errors) = 'array')
);

CREATE TABLE truelock.investigation_step_input_evidence (
    step_id uuid NOT NULL REFERENCES truelock.investigation_steps(step_id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES truelock.evidence(evidence_id) ON DELETE RESTRICT,
    PRIMARY KEY (step_id, evidence_id)
);

CREATE TABLE truelock.investigation_step_result_evidence (
    step_id uuid NOT NULL REFERENCES truelock.investigation_steps(step_id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES truelock.evidence(evidence_id) ON DELETE RESTRICT,
    PRIMARY KEY (step_id, evidence_id)
);

CREATE TABLE truelock.exposure_calculations (
    exposure_calculation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE RESTRICT,
    calculation_version text NOT NULL,
    allocation_method text NOT NULL,
    base_currency char(3) NOT NULL DEFAULT 'MXN',
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    calculated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT exposure_parameters_object CHECK (jsonb_typeof(parameters) = 'object'),
    CONSTRAINT exposure_limitations_array CHECK (jsonb_typeof(limitations) = 'array')
);

CREATE TABLE truelock.exposure_components (
    exposure_component_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exposure_calculation_id uuid NOT NULL
        REFERENCES truelock.exposure_calculations(exposure_calculation_id) ON DELETE CASCADE,
    root_flow_id text NOT NULL,
    component_type truelock.exposure_component_type NOT NULL,
    source_record_type truelock.record_type NOT NULL,
    source_record_id uuid NOT NULL,
    root_bank_transaction_id uuid REFERENCES truelock.bank_transactions(bank_transaction_id),
    parent_component_id uuid REFERENCES truelock.exposure_components(exposure_component_id),
    amount_mxn numeric(20,6) NOT NULL CHECK (amount_mxn >= 0),
    occurred_at timestamptz,
    path_sequence integer CHECK (path_sequence IS NULL OR path_sequence >= 0),
    is_supported boolean NOT NULL DEFAULT true,
    allocation_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT exposure_component_identity_uq UNIQUE (
        exposure_calculation_id, root_flow_id, component_type,
        source_record_type, source_record_id
    ),
    CONSTRAINT exposure_allocation_details_object CHECK (
        jsonb_typeof(allocation_details) = 'object'
    )
);

-- A root flow is counted once even when the same money appears on multiple downstream edges.
CREATE UNIQUE INDEX exposure_one_root_component_uq
    ON truelock.exposure_components (exposure_calculation_id, root_flow_id)
    WHERE component_type = 'ROOT';

CREATE VIEW truelock.v_exposure_summary AS
SELECT
    ec.exposure_calculation_id,
    ec.case_id,
    ec.base_currency,
    coalesce(sum(c.amount_mxn) FILTER (
        WHERE c.component_type = 'ROOT' AND c.is_supported
    ), 0) AS supported_root_exposure_mxn,
    coalesce(sum(c.amount_mxn) FILTER (
        WHERE c.component_type = 'DOWNSTREAM' AND c.is_supported
    ), 0) AS downstream_traced_mxn,
    coalesce(sum(c.amount_mxn) FILTER (
        WHERE c.component_type IN ('RETURNED', 'RECOVERED') AND c.is_supported
    ), 0) AS returned_or_recovered_mxn,
    coalesce(sum(c.amount_mxn) FILTER (
        WHERE c.component_type = 'CREDIT' AND c.is_supported
    ), 0) AS credits_mxn,
    greatest(
        coalesce(sum(c.amount_mxn) FILTER (
            WHERE c.component_type = 'ROOT' AND c.is_supported
        ), 0)
        - coalesce(sum(c.amount_mxn) FILTER (
            WHERE c.component_type IN ('RETURNED', 'RECOVERED') AND c.is_supported
        ), 0)
        - coalesce(sum(c.amount_mxn) FILTER (
            WHERE c.component_type = 'CREDIT' AND c.is_supported
        ), 0),
        0
    ) AS net_supported_exposure_mxn
FROM truelock.exposure_calculations ec
LEFT JOIN truelock.exposure_components c
  ON c.exposure_calculation_id = ec.exposure_calculation_id
GROUP BY ec.exposure_calculation_id, ec.case_id, ec.base_currency;

CREATE TABLE truelock.findings (
    finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE RESTRICT,
    thread_id uuid NOT NULL REFERENCES truelock.investigation_threads(thread_id) ON DELETE RESTRICT,
    display_id text NOT NULL,
    scheme_code text NOT NULL,
    claim text NOT NULL,
    status truelock.finding_status NOT NULL DEFAULT 'DRAFT',
    confidence_label truelock.confidence_label NOT NULL,
    exposure_calculation_id uuid
        REFERENCES truelock.exposure_calculations(exposure_calculation_id) ON DELETE RESTRICT,
    supported_exposure_mxn numeric(20,6) CHECK (
        supported_exposure_mxn IS NULL OR supported_exposure_mxn >= 0
    ),
    downstream_flow_mxn numeric(20,6) CHECK (
        downstream_flow_mxn IS NULL OR downstream_flow_mxn >= 0
    ),
    coverage_sufficient boolean NOT NULL DEFAULT false,
    unresolved_material_contradiction boolean NOT NULL DEFAULT false,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    retracted_at timestamptz,
    retraction_reason text,
    CONSTRAINT findings_case_display_uq UNIQUE (case_id, display_id),
    CONSTRAINT findings_limitations_array CHECK (jsonb_typeof(limitations) = 'array'),
    CONSTRAINT findings_retraction_reason CHECK (
        status <> 'RETRACTED' OR (retracted_at IS NOT NULL AND retraction_reason IS NOT NULL)
    )
);

CREATE TABLE truelock.finding_entities (
    finding_id uuid NOT NULL REFERENCES truelock.findings(finding_id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES truelock.entities(entity_id) ON DELETE RESTRICT,
    role text NOT NULL,
    PRIMARY KEY (finding_id, entity_id, role)
);

CREATE TABLE truelock.finding_root_transactions (
    finding_id uuid NOT NULL REFERENCES truelock.findings(finding_id) ON DELETE CASCADE,
    bank_transaction_id uuid NOT NULL
        REFERENCES truelock.bank_transactions(bank_transaction_id) ON DELETE RESTRICT,
    root_flow_id text NOT NULL,
    PRIMARY KEY (finding_id, bank_transaction_id),
    CONSTRAINT finding_root_flow_uq UNIQUE (finding_id, root_flow_id)
);

CREATE TABLE truelock.finding_evidence (
    finding_id uuid NOT NULL REFERENCES truelock.findings(finding_id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES truelock.evidence(evidence_id) ON DELETE RESTRICT,
    role truelock.evidence_role NOT NULL DEFAULT 'SUPPORTING',
    PRIMARY KEY (finding_id, evidence_id)
);

CREATE TABLE truelock.case_questions (
    question_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES truelock.cases(case_id) ON DELETE CASCADE,
    question text NOT NULL,
    answer text NOT NULL,
    certainty text NOT NULL,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    asked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    answered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT case_questions_limitations_array CHECK (jsonb_typeof(limitations) = 'array')
);

CREATE TABLE truelock.case_question_evidence (
    question_id uuid NOT NULL REFERENCES truelock.case_questions(question_id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES truelock.evidence(evidence_id) ON DELETE RESTRICT,
    PRIMARY KEY (question_id, evidence_id)
);

CREATE TABLE truelock.case_question_steps (
    question_id uuid NOT NULL REFERENCES truelock.case_questions(question_id) ON DELETE CASCADE,
    step_id uuid NOT NULL REFERENCES truelock.investigation_steps(step_id) ON DELETE RESTRICT,
    PRIMARY KEY (question_id, step_id)
);

CREATE OR REPLACE FUNCTION truelock.prevent_audit_record_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; create a superseding record instead', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER evidence_append_only
BEFORE UPDATE OR DELETE ON truelock.evidence
FOR EACH ROW EXECUTE FUNCTION truelock.prevent_audit_record_mutation();

CREATE TRIGGER investigation_steps_append_only
BEFORE UPDATE OR DELETE ON truelock.investigation_steps
FOR EACH ROW EXECUTE FUNCTION truelock.prevent_audit_record_mutation();

CREATE OR REPLACE FUNCTION truelock.validate_supported_finding(target_finding_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    f truelock.findings%ROWTYPE;
    evidence_count integer;
    exposure_amount numeric(20,6);
BEGIN
    SELECT * INTO f FROM truelock.findings WHERE finding_id = target_finding_id;
    IF NOT FOUND OR f.status <> 'SUPPORTED' THEN
        RETURN;
    END IF;

    SELECT count(*) INTO evidence_count
    FROM truelock.finding_evidence fe
    JOIN truelock.evidence e ON e.evidence_id = fe.evidence_id
    WHERE fe.finding_id = f.finding_id
      AND fe.role IN ('SUPPORTING', 'CONTEXTUAL')
      AND e.case_id = f.case_id;

    IF evidence_count < 2 THEN
        RAISE EXCEPTION 'SUPPORTED finding % requires at least two case-scoped evidence records', f.finding_id;
    END IF;
    IF NOT f.coverage_sufficient THEN
        RAISE EXCEPTION 'SUPPORTED finding % requires sufficient data coverage', f.finding_id;
    END IF;
    IF f.unresolved_material_contradiction THEN
        RAISE EXCEPTION 'SUPPORTED finding % has an unresolved material contradiction', f.finding_id;
    END IF;
    IF f.exposure_calculation_id IS NULL OR f.supported_exposure_mxn IS NULL THEN
        RAISE EXCEPTION 'SUPPORTED finding % requires deterministic exposure', f.finding_id;
    END IF;

    SELECT supported_root_exposure_mxn INTO exposure_amount
    FROM truelock.v_exposure_summary
    WHERE exposure_calculation_id = f.exposure_calculation_id
      AND case_id = f.case_id;

    IF exposure_amount IS NULL OR abs(exposure_amount - f.supported_exposure_mxn) > 0.01 THEN
        RAISE EXCEPTION 'Finding % exposure does not match its deterministic calculation', f.finding_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION truelock.validate_supported_finding_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM truelock.validate_supported_finding(COALESCE(NEW.finding_id, OLD.finding_id));
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE CONSTRAINT TRIGGER findings_supported_gate
AFTER INSERT OR UPDATE ON truelock.findings
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION truelock.validate_supported_finding_trigger();

CREATE CONSTRAINT TRIGGER finding_evidence_supported_gate
AFTER INSERT OR UPDATE OR DELETE ON truelock.finding_evidence
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION truelock.validate_supported_finding_trigger();

CREATE INDEX investigations_case_lead_idx
    ON truelock.investigations (case_id, lead_id, status);
CREATE INDEX investigation_threads_case_status_idx
    ON truelock.investigation_threads (case_id, status);
CREATE INDEX evidence_case_type_idx ON truelock.evidence (case_id, evidence_type);
CREATE INDEX evidence_source_idx ON truelock.evidence (source_file_id, source_locator);
CREATE INDEX investigation_steps_thread_sequence_idx
    ON truelock.investigation_steps (thread_id, sequence);
CREATE INDEX findings_case_status_idx ON truelock.findings (case_id, status);
CREATE INDEX exposure_components_calc_flow_idx
    ON truelock.exposure_components (exposure_calculation_id, root_flow_id, path_sequence);

INSERT INTO truelock.schema_migrations(version) VALUES ('0006_canonical_investigation_evidence_and_exposure');
