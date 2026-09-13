\set ON_ERROR_STOP on

DO $$
DECLARE
    actual_count integer;
    bad_count integer;
BEGIN
    SELECT count(*) INTO actual_count FROM truelock.schema_migrations;
    IF actual_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 migrations, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.source_files
    WHERE case_id = '10000000-0000-0000-0000-000000000001';
    IF actual_count < 6 THEN
        RAISE EXCEPTION 'Expected at least 6 demo source files, found %', actual_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM truelock.v_invoice_settlement
    WHERE case_id = '10000000-0000-0000-0000-000000000001'
      AND settlement_status <> 'SETTLED';
    IF bad_count <> 0 THEN
        RAISE EXCEPTION 'All demo invoices must reconcile; % do not', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM truelock.v_ledger_entry_balance
    WHERE case_id = '10000000-0000-0000-0000-000000000001'
      AND NOT is_balanced;
    IF bad_count <> 0 THEN
        RAISE EXCEPTION 'All demo journal entries must balance; % do not', bad_count;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.trace_bank_paths(
        '10000000-0000-0000-0000-000000000001',
        '70000000-0000-0000-0000-000000000001',
        4,
        interval '30 days'
    )
    WHERE depth = 3
      AND bank_transaction_id = '70000000-0000-0000-0000-000000000003';
    IF actual_count <> 1 THEN
        RAISE EXCEPTION 'Expected one three-edge return path, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.bank_transactions
    WHERE case_id = '10000000-0000-0000-0000-000000000001'
      AND external_transaction_id IN ('TX-ROOT-001', 'TX-HOP-001', 'TX-RET-001');
    IF actual_count <> 3 THEN
        RAISE EXCEPTION 'Canonical cycle transactions missing, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.entities
    WHERE case_id = '10000000-0000-0000-0000-000000000001'
      AND rfc IN ('EDE180101AA1', 'CPR190515BB2', 'LSF200820CC3', 'PCR150310AA1', 'CRL170822BB2');
    IF actual_count <> 5 THEN
        RAISE EXCEPTION 'Canonical RFCs missing, found %', actual_count;
    END IF;
END;
$$;

DO $$
DECLARE
    summary record;
    actual_count integer;
BEGIN
    SELECT * INTO summary
    FROM truelock.v_exposure_summary
    WHERE exposure_calculation_id = '12000000-0000-0000-0000-000000000001';

    IF summary.supported_root_exposure_mxn <> 1000000 THEN
        RAISE EXCEPTION 'Root exposure should be 1000000, got %', summary.supported_root_exposure_mxn;
    END IF;
    IF summary.downstream_traced_mxn <> 920000 THEN
        RAISE EXCEPTION 'Downstream flow should be 920000, got %', summary.downstream_traced_mxn;
    END IF;
    IF summary.returned_or_recovered_mxn <> 740000 THEN
        RAISE EXCEPTION 'Returned amount should be 740000, got %', summary.returned_or_recovered_mxn;
    END IF;
    IF summary.net_supported_exposure_mxn <> 260000 THEN
        RAISE EXCEPTION 'Net exposure should be 260000, got %', summary.net_supported_exposure_mxn;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.exposure_components
    WHERE exposure_calculation_id = '12000000-0000-0000-0000-000000000001'
      AND root_flow_id = 'RF-001'
      AND component_type = 'ROOT';
    IF actual_count <> 1 THEN
        RAISE EXCEPTION 'Root flow must be counted exactly once, got % roots', actual_count;
    END IF;
END;
$$;

DO $$
DECLARE
    actual_count integer;
BEGIN
    SELECT count(*) INTO actual_count
    FROM truelock.findings f
    WHERE f.case_id = '10000000-0000-0000-0000-000000000001'
      AND f.status = 'SUPPORTED';
    IF actual_count <> 1 THEN
        RAISE EXCEPTION 'Expected exactly one supported finding, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.leads l
    WHERE l.case_id = '10000000-0000-0000-0000-000000000001'
      AND l.status = 'REJECTED';
    IF actual_count <> 1 THEN
        RAISE EXCEPTION 'Expected exactly one rejected control lead, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.findings f
    JOIN truelock.investigation_threads t ON t.thread_id = f.thread_id
    JOIN truelock.investigations i ON i.investigation_id = t.investigation_id
    JOIN truelock.leads l ON l.lead_id = i.lead_id
    WHERE l.status = 'REJECTED';
    IF actual_count <> 0 THEN
        RAISE EXCEPTION 'A rejected lead must not have a finding';
    END IF;

    SELECT count(*) INTO actual_count
    FROM truelock.finding_evidence
    WHERE finding_id = '14000000-0000-0000-0000-000000000001';
    IF actual_count < 2 THEN
        RAISE EXCEPTION 'Supported finding needs at least two evidence records';
    END IF;
END;
$$;

DO $$
BEGIN
    BEGIN
        UPDATE truelock.evidence
        SET created_by = 'illegal-mutation'
        WHERE evidence_id = 'f0000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'Evidence append-only trigger did not fire';
    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM = 'Evidence append-only trigger did not fire' THEN
                RAISE;
            END IF;
    END;
END;
$$;

DO $$
BEGIN
    BEGIN
        INSERT INTO truelock.findings (
            finding_id, case_id, thread_id, display_id, scheme_code, claim,
            status, confidence_label, exposure_calculation_id,
            supported_exposure_mxn, coverage_sufficient
        )
        VALUES (
            'ffffffff-ffff-4fff-8fff-ffffffffffff',
            '10000000-0000-0000-0000-000000000001',
            'e0000000-0000-0000-0000-000000000001',
            'INVALID-TEST', 'ROUND_TRIPPING',
            'This row deliberately has no linked evidence.',
            'SUPPORTED', 'HIGH',
            '12000000-0000-0000-0000-000000000001', 1000000, true
        );

        PERFORM truelock.validate_supported_finding(
            'ffffffff-ffff-4fff-8fff-ffffffffffff'
        );
        RAISE EXCEPTION 'Supported-finding gate did not reject missing evidence';
    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM = 'Supported-finding gate did not reject missing evidence' THEN
                RAISE;
            END IF;
    END;
END;
$$;

SELECT
    'PASS' AS status,
    'All TrueLock database demo invariants hold' AS message;
