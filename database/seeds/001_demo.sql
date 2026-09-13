BEGIN;

INSERT INTO truelock.organizations (organization_id, legal_name, rfc)
VALUES ('00000000-0000-0000-0000-000000000001', 'TrueLock Demo Company SA de CV', 'TDC260101AB1');

INSERT INTO truelock.cases (
    case_id, organization_id, display_id, title, status, base_currency, metadata
)
VALUES (
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'CASE-DEMO-001',
    'Round-trip with legitimate control supplier',
    'COMPLETED',
    'MXN',
    '{"fixture":"canonical-demo-v1","expected_supported_findings":1,"expected_rejected_leads":1}'
);

INSERT INTO truelock.source_files (
    source_file_id, case_id, original_filename, dataset_kind, media_type,
    byte_size, sha256, parser_name, parser_version, status, record_count, ingested_at
)
VALUES
    ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'suppliers.csv', 'SUPPLIER_MASTER', 'text/csv', 1000, repeat('1',64),
     'supplier_csv', '1.0.0', 'IMPORTED', 2, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'invoices.xml', 'CFDI_INVOICE', 'application/xml', 2000, repeat('2',64),
     'cfdi_4_xml', '1.0.0', 'IMPORTED', 2, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'bank.csv', 'BANK', 'text/csv', 3000, repeat('3',64),
     'bank_csv', '1.0.0', 'IMPORTED', 5, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'ledger.csv', 'LEDGER', 'text/csv', 3000, repeat('4',64),
     'ledger_csv', '1.0.0', 'IMPORTED', 8, clock_timestamp());

INSERT INTO truelock.case_source_files (case_id, source_file_id)
SELECT '10000000-0000-0000-0000-000000000001', source_file_id
FROM truelock.source_files
WHERE case_id = '10000000-0000-0000-0000-000000000001';

INSERT INTO truelock.data_coverage (
    case_id, source_file_id, dataset_kind, covered_from, covered_to,
    is_complete, completeness_reason, timezone_name, sign_convention
)
SELECT
    case_id,
    source_file_id,
    dataset_kind,
    '2026-01-01T00:00:00-06:00'::timestamptz,
    '2026-01-31T23:59:59-06:00'::timestamptz,
    true,
    'Synthetic fixture declares complete January coverage',
    'America/Mexico_City',
    CASE WHEN dataset_kind = 'BANK' THEN 'SEPARATE_DIRECTION' ELSE NULL END
FROM truelock.source_files
WHERE case_id = '10000000-0000-0000-0000-000000000001';

INSERT INTO truelock.entities (
    entity_id, case_id, entity_type, canonical_name, legal_name, rfc,
    source_file_id, source_locator
)
VALUES
    ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'COMPANY', 'TrueLock Demo Company SA de CV', 'TrueLock Demo Company SA de CV', 'TDC260101AB1',
     '20000000-0000-0000-0000-000000000001', 'organization:1'),
    ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'SUPPLIER', 'Proveedor Alfa SA de CV', 'Proveedor Alfa SA de CV', 'PAL260101AB1',
     '20000000-0000-0000-0000-000000000001', 'row:2'),
    ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'UNKNOWN', 'Intermediaria Beta SA de CV', 'Intermediaria Beta SA de CV', 'IBE260101AB1',
     '20000000-0000-0000-0000-000000000003', 'counterparty:IBE260101AB1'),
    ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'UNKNOWN', 'Cuenta Relacionada Gamma', 'Cuenta Relacionada Gamma', 'CRG260101AB1',
     '20000000-0000-0000-0000-000000000003', 'counterparty:CRG260101AB1'),
    ('30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     'SUPPLIER', 'Infraestructura Legítima SA de CV', 'Infraestructura Legítima SA de CV', 'ILE260101AB1',
     '20000000-0000-0000-0000-000000000001', 'row:3');

INSERT INTO truelock.entity_identifiers (
    case_id, entity_id, identifier_type, identifier_value, normalized_value,
    source_file_id, source_locator, confidence, is_merge_key
)
SELECT
    case_id, entity_id, 'RFC', rfc, rfc, source_file_id, source_locator, 1.0, true
FROM truelock.entities
WHERE case_id = '10000000-0000-0000-0000-000000000001';

INSERT INTO truelock.bank_accounts (
    bank_account_id, case_id, account_fingerprint, account_number, masked_account,
    bank_name, currency, source_file_id
)
VALUES
    ('40000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     repeat('a',64), '000000000000000001', '**************0001', 'Demo Bank', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     repeat('b',64), '000000000000000002', '**************0002', 'Demo Bank', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     repeat('c',64), '000000000000000003', '**************0003', 'Demo Bank', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     repeat('d',64), '000000000000000004', '**************0004', 'Demo Bank', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     repeat('e',64), '000000000000000005', '**************0005', 'Demo Bank', 'MXN',
     '20000000-0000-0000-0000-000000000003');

INSERT INTO truelock.entity_bank_accounts (entity_id, bank_account_id, is_primary, source_file_id, source_locator)
VALUES
    ('30000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', true,
     '20000000-0000-0000-0000-000000000003', 'account:1'),
    ('30000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000002', true,
     '20000000-0000-0000-0000-000000000001', 'row:2'),
    ('30000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000003', true,
     '20000000-0000-0000-0000-000000000003', 'counterparty:3'),
    ('30000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000004', true,
     '20000000-0000-0000-0000-000000000003', 'counterparty:4'),
    ('30000000-0000-0000-0000-000000000005', '40000000-0000-0000-0000-000000000005', true,
     '20000000-0000-0000-0000-000000000001', 'row:3');

INSERT INTO truelock.suppliers (
    supplier_id, case_id, entity_id, external_supplier_id, legal_name, rfc,
    address_raw, address_normalized, created_at_source, category,
    source_file_id, source_locator, record_sha256
)
VALUES
    ('50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000002', 'SUP-001', 'Proveedor Alfa SA de CV', 'PAL260101AB1',
     'Av Demo 10', 'AV DEMO 10', '2025-12-20T10:00:00-06:00', 'CONSULTING',
     '20000000-0000-0000-0000-000000000001', 'row:2', repeat('5',64)),
    ('50000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000005', 'SUP-002', 'Infraestructura Legítima SA de CV', 'ILE260101AB1',
     'Parque Industrial 100', 'PARQUE INDUSTRIAL 100', '2025-12-22T10:00:00-06:00', 'INFRASTRUCTURE',
     '20000000-0000-0000-0000-000000000001', 'row:3', repeat('6',64));

INSERT INTO truelock.invoices (
    invoice_id, case_id, source_file_id, source_locator, record_sha256,
    uuid, version, issue_timestamp, issuer_entity_id, receiver_entity_id,
    rfc_issuer, issuer_name, rfc_receiver, receiver_name, subtotal, tax_total,
    total, currency, amount_mxn, cfdi_type, payment_method, cfdi_status,
    raw_xml_sha256
)
VALUES
    ('60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000002', 'xml:invoice:1', repeat('7',64),
     'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', '4.0', '2026-01-10T08:00:00-06:00',
     '30000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000001',
     'PAL260101AB1', 'Proveedor Alfa SA de CV', 'TDC260101AB1', 'TrueLock Demo Company SA de CV',
     862068.965517, 137931.034483, 1000000, 'MXN', 1000000, 'I', 'PUE', 'ACTIVE', repeat('8',64)),
    ('60000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000002', 'xml:invoice:2', repeat('9',64),
     'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB', '4.0', '2026-01-15T08:00:00-06:00',
     '30000000-0000-0000-0000-000000000005', '30000000-0000-0000-0000-000000000001',
     'ILE260101AB1', 'Infraestructura Legítima SA de CV', 'TDC260101AB1', 'TrueLock Demo Company SA de CV',
     4310344.827586, 689655.172414, 5000000, 'MXN', 5000000, 'I', 'PUE', 'ACTIVE', repeat('0',64));

INSERT INTO truelock.invoice_concepts (
    invoice_id, line_no, product_service_code, quantity, description, unit_value, amount
)
VALUES
    ('60000000-0000-0000-0000-000000000001', 1, '80101500', 1,
     'Consulting services', 862068.965517, 862068.965517),
    ('60000000-0000-0000-0000-000000000002', 1, '72150000', 1,
     'Documented data-center infrastructure project', 4310344.827586, 4310344.827586);

INSERT INTO truelock.bank_transactions (
    bank_transaction_id, case_id, source_file_id, source_locator,
    external_transaction_id, observed_bank_account_id, booked_at, value_date,
    direction, origin_bank_account_id, destination_bank_account_id,
    origin_entity_id, destination_entity_id, amount, currency, amount_mxn,
    reference, concept, record_sha256
)
VALUES
    ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:2', 'TX-ROOT-001',
     '40000000-0000-0000-0000-000000000001', '2026-01-10T10:00:00-06:00', '2026-01-10', 'DEBIT',
     '40000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000002',
     '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002',
     1000000, 'MXN', 1000000, 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', 'Invoice payment', repeat('a',64)),
    ('70000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:3', 'TX-HOP-002',
     '40000000-0000-0000-0000-000000000002', '2026-01-10T12:00:00-06:00', '2026-01-10', 'DEBIT',
     '40000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000003',
     '30000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000003',
     920000, 'MXN', 920000, 'TRANSFER-ALFA-BETA', 'Treasury transfer', repeat('b',64)),
    ('70000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:4', 'TX-HOP-003',
     '40000000-0000-0000-0000-000000000003', '2026-01-10T14:00:00-06:00', '2026-01-10', 'DEBIT',
     '40000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000004',
     '30000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000004',
     740000, 'MXN', 740000, 'TRANSFER-BETA-GAMMA', 'Related transfer', repeat('c',64)),
    ('70000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:5', 'TX-RETURN-004',
     '40000000-0000-0000-0000-000000000004', '2026-01-10T16:00:00-06:00', '2026-01-10', 'CREDIT',
     '40000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000001',
     740000, 'MXN', 740000, 'TRANSFER-GAMMA-COMPANY', 'Return transfer', repeat('d',64)),
    ('70000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:6', 'TX-LEGIT-005',
     '40000000-0000-0000-0000-000000000001', '2026-01-15T10:00:00-06:00', '2026-01-15', 'DEBIT',
     '40000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000005',
     '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000005',
     5000000, 'MXN', 5000000, 'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB',
     'Documented infrastructure project', repeat('e',64));

INSERT INTO truelock.ledger_entries (
    journal_line_id, case_id, source_file_id, source_locator, journal_entry_id,
    posting_date, account_code, account_name, account_type, debit, credit,
    currency, base_amount_mxn, supplier_id, invoice_id, invoice_uuid, description
)
VALUES
    ('80000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:2', 'JE-001', '2026-01-10', '6100', 'Consulting expense', 'EXPENSE', 1000000, 0, 'MXN', 1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', 'Book vendor invoice'),
    ('80000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:3', 'JE-001', '2026-01-10', '2100', 'Accounts payable', 'LIABILITY', 0, 1000000, 'MXN', -1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', 'Book vendor invoice'),
    ('80000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:4', 'JE-002', '2026-01-10', '2100', 'Accounts payable', 'LIABILITY', 1000000, 0, 'MXN', 1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', 'Settle vendor invoice'),
    ('80000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:5', 'JE-002', '2026-01-10', '1100', 'Cash', 'ASSET', 0, 1000000, 'MXN', -1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA', 'Settle vendor invoice'),
    ('80000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:6', 'JE-003', '2026-01-15', '6200', 'Infrastructure expense', 'EXPENSE', 5000000, 0, 'MXN', 5000000, '50000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000002', 'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB', 'Book legitimate invoice'),
    ('80000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:7', 'JE-003', '2026-01-15', '2100', 'Accounts payable', 'LIABILITY', 0, 5000000, 'MXN', -5000000, '50000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000002', 'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB', 'Book legitimate invoice'),
    ('80000000-0000-0000-0000-000000000007', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:8', 'JE-004', '2026-01-15', '2100', 'Accounts payable', 'LIABILITY', 5000000, 0, 'MXN', 5000000, '50000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000002', 'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB', 'Settle legitimate invoice'),
    ('80000000-0000-0000-0000-000000000008', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:9', 'JE-004', '2026-01-15', '1100', 'Cash', 'ASSET', 0, 5000000, 'MXN', -5000000, '50000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000002', 'BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB', 'Settle legitimate invoice');

INSERT INTO truelock.reconciliation_matches (
    reconciliation_match_id, case_id, match_type, status, confidence,
    matched_amount, currency, amount_mxn, rules, explanation, created_by
)
VALUES
    ('90000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'UUID_AMOUNT_SUPPLIER_TIME', 'CONFIRMED', 'HIGH', 1000000, 'MXN', 1000000,
     '["UUID_EXACT","AMOUNT_EXACT","SUPPLIER_EXACT","TIME_DELTA_2H"]',
     'Invoice UUID appears in bank reference and amount and supplier match.', 'seed-reconciler-v1'),
    ('90000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'UUID_AMOUNT_SUPPLIER_TIME', 'CONFIRMED', 'HIGH', 5000000, 'MXN', 5000000,
     '["UUID_EXACT","AMOUNT_EXACT","SUPPLIER_EXACT","TIME_DELTA_2H"]',
     'Legitimate control invoice reconciles exactly to its bank payment.', 'seed-reconciler-v1');

INSERT INTO truelock.reconciliation_invoice_allocations (reconciliation_match_id, invoice_id, allocated_amount)
VALUES
    ('90000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 1000000),
    ('90000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000002', 5000000);

INSERT INTO truelock.reconciliation_bank_allocations (reconciliation_match_id, bank_transaction_id, allocated_amount)
VALUES
    ('90000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', 1000000),
    ('90000000-0000-0000-0000-000000000002', '70000000-0000-0000-0000-000000000005', 5000000);

INSERT INTO truelock.detector_runs (
    detector_run_id, case_id, detector_code, detector_version, parameters,
    status, finished_at, records_scanned, anomalies_emitted
)
VALUES
    ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'RAPID_PASS_THROUGH', '1.0.0', '{"ratio":0.8,"window_hours":24}',
     'COMPLETED', clock_timestamp(), 5, 1),
    ('a0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'CYCLE', '1.0.0', '{"max_depth":4,"window_days":30}',
     'COMPLETED', clock_timestamp(), 5, 1),
    ('a0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'NEW_VENDOR_HIGH_SPEND', '1.0.0', '{"max_vendor_age_days":30}',
     'COMPLETED', clock_timestamp(), 2, 1);

INSERT INTO truelock.anomalies (
    anomaly_id, case_id, detector_run_id, detector_code, status,
    title, description, strength, amount_mxn, occurred_at, details
)
VALUES
    ('b0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000001', 'RAPID_PASS_THROUGH', 'GROUPED_INTO_LEAD',
     '92% moved within two hours', 'Proveedor Alfa moved MXN 920,000 shortly after receipt.',
     0.92, 920000, '2026-01-10T12:00:00-06:00', '{"ratio":0.92,"elapsed_hours":2}'),
    ('b0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000002', 'CYCLE', 'GROUPED_INTO_LEAD',
     'Time-respecting four-edge cycle', 'Funds returned to the originating company within six hours.',
     0.95, 740000, '2026-01-10T16:00:00-06:00', '{"depth":4,"returned_amount_mxn":740000}'),
    ('b0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000003', 'NEW_VENDOR_HIGH_SPEND', 'GROUPED_INTO_LEAD',
     'New vendor received MXN 5,000,000', 'Large spend with recently onboarded infrastructure vendor.',
     0.70, 5000000, '2026-01-15T10:00:00-06:00', '{"vendor_age_days":24}');

INSERT INTO truelock.anomaly_records (anomaly_id, record_type, record_id, role, source_file_id, source_locator)
VALUES
    ('b0000000-0000-0000-0000-000000000001', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000001', 'INFLOW', '20000000-0000-0000-0000-000000000003', 'row:2'),
    ('b0000000-0000-0000-0000-000000000001', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000002', 'OUTFLOW', '20000000-0000-0000-0000-000000000003', 'row:3'),
    ('b0000000-0000-0000-0000-000000000002', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000004', 'RETURN', '20000000-0000-0000-0000-000000000003', 'row:5'),
    ('b0000000-0000-0000-0000-000000000003', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000005', 'PAYMENT', '20000000-0000-0000-0000-000000000003', 'row:6');

INSERT INTO truelock.leads (
    lead_id, case_id, display_id, title, risk_score, risk_score_version,
    priority, status, reason_summary
)
VALUES
    ('c0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'L001', 'Proveedor Alfa round-trip', 92, 'demo-v1', 'CRITICAL', 'SUPPORTED',
     'Independent rapid-pass-through and cycle signals justify investigation.'),
    ('c0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'L002', 'Large spend with new infrastructure vendor', 35, 'demo-v1', 'MEDIUM', 'REJECTED',
     'Large amount and recent onboarding were reviewed, but records support a legitimate transaction.');

INSERT INTO truelock.lead_anomalies (lead_id, anomaly_id)
VALUES
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002'),
    ('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003');

INSERT INTO truelock.lead_entities (lead_id, entity_id, role)
VALUES
    ('c0000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', 'SUBJECT'),
    ('c0000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000005', 'SUBJECT');

INSERT INTO truelock.investigations (
    investigation_id, case_id, lead_id, status, model_provider, model_name,
    tool_calls_used, started_at, completed_at
)
VALUES
    ('d0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'c0000000-0000-0000-0000-000000000001', 'COMPLETED', 'fixture', 'deterministic-seed',
     3, '2026-01-31T10:00:00Z', '2026-01-31T10:00:03Z'),
    ('d0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'c0000000-0000-0000-0000-000000000002', 'COMPLETED', 'fixture', 'deterministic-seed',
     2, '2026-01-31T10:01:00Z', '2026-01-31T10:01:02Z');

INSERT INTO truelock.investigation_threads (
    thread_id, investigation_id, case_id, display_id, scheme_code,
    hypothesis_claim, status, tool_calls_used, last_new_evidence_sequence,
    outcome_reason, created_at, closed_at
)
VALUES
    ('e0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000001', 'T001', 'ROUND_TRIPPING',
     'Proveedor Alfa may be a pass-through in a time-respecting round trip.',
     'SUPPORTED', 3, 3, 'The bank path returns MXN 740,000 to the originating company.',
     '2026-01-31T10:00:00Z', '2026-01-31T10:00:03Z'),
    ('e0000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000002',
     '10000000-0000-0000-0000-000000000001', 'T002', 'NEW_VENDOR_HIGH_SPEND',
     'The new infrastructure vendor may be unsupported.',
     'REJECTED', 2, 2,
     'Invoice, bank settlement and balanced ledger agree; no suspicious downstream flow exists.',
     '2026-01-31T10:01:00Z', '2026-01-31T10:01:02Z');

INSERT INTO truelock.evidence (
    evidence_id, case_id, evidence_type, record_id, source_file_id,
    source_locator, source_record_sha256, facts, created_by
)
VALUES
    ('f0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'INVOICE', '60000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
     'xml:invoice:1', repeat('7',64), '{"uuid":"AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA","total_mxn":1000000}', 'get_invoice'),
    ('f0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000003',
     'row:2', repeat('a',64), '{"amount_mxn":1000000,"timestamp":"2026-01-10T10:00:00-06:00","role":"ROOT"}', 'trace_money'),
    ('f0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000003',
     'row:3', repeat('b',64), '{"amount_mxn":920000,"elapsed_hours":2,"role":"DOWNSTREAM"}', 'trace_money'),
    ('f0000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000004', '20000000-0000-0000-0000-000000000003',
     'row:5', repeat('d',64), '{"amount_mxn":740000,"elapsed_hours":6,"role":"RETURNED"}', 'trace_money'),
    ('f0000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     'INVOICE', '60000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002',
     'xml:invoice:2', repeat('9',64), '{"uuid":"BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB","total_mxn":5000000,"status":"ACTIVE"}', 'get_invoice'),
    ('f0000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000001',
     'RECONCILIATION_MATCH', '90000000-0000-0000-0000-000000000002', NULL,
     'reconciliation:M002', NULL, '{"matched_amount_mxn":5000000,"confidence":"HIGH","status":"CONFIRMED"}', 'match_invoice_payment');

INSERT INTO truelock.thread_evidence (thread_id, evidence_id, role, assertion_code)
VALUES
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000001', 'CONTEXTUAL', 'ROOT_INVOICE'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000002', 'SUPPORTING', 'ROOT_PAYMENT'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000003', 'SUPPORTING', 'RAPID_OUTFLOW'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000004', 'SUPPORTING', 'RETURN_TO_ORIGIN'),
    ('e0000000-0000-0000-0000-000000000002', 'f0000000-0000-0000-0000-000000000005', 'MITIGATING', 'VALID_INVOICE'),
    ('e0000000-0000-0000-0000-000000000002', 'f0000000-0000-0000-0000-000000000006', 'CONTRADICTING', 'EXACT_SETTLEMENT');

INSERT INTO truelock.investigation_steps (
    step_id, case_id, investigation_id, thread_id, sequence, action, tool_name,
    reason_summary, tool_inputs, result_summary, provenance, decision,
    started_at, completed_at, duration_ms
)
VALUES
    ('11000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 1,
     'MATCH_INVOICE_PAYMENT', 'match_invoice_payment',
     'Confirm whether the root transfer settled a real invoice.',
     '{"invoice_id":"60000000-0000-0000-0000-000000000001"}',
     '{"match_id":"90000000-0000-0000-0000-000000000001","confidence":"HIGH"}',
     '{"source_ids":["60000000-0000-0000-0000-000000000001","70000000-0000-0000-0000-000000000001"]}',
     'CONTINUE', '2026-01-31T10:00:00Z', '2026-01-31T10:00:00.400Z', 400),
    ('11000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 2,
     'TRACE_MONEY', 'trace_money',
     'The supplier moved 92% of the root payment within two hours.',
     '{"start_transaction_id":"70000000-0000-0000-0000-000000000001","max_depth":4}',
     '{"path_transaction_ids":["70000000-0000-0000-0000-000000000001","70000000-0000-0000-0000-000000000002","70000000-0000-0000-0000-000000000003","70000000-0000-0000-0000-000000000004"]}',
     '{"source_file_id":"20000000-0000-0000-0000-000000000003"}',
     'CONTINUE', '2026-01-31T10:00:00.500Z', '2026-01-31T10:00:02Z', 1500),
    ('11000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 3,
     'TEST_HYPOTHESIS', NULL,
     'The time-respecting path returns supported funds to the originating company.',
     '{}', '{"outcome":"SUPPORTED"}', '{"evidence_ids":["f0000000-0000-0000-0000-000000000002","f0000000-0000-0000-0000-000000000004"]}',
     'SUPPORT', '2026-01-31T10:00:02.100Z', '2026-01-31T10:00:03Z', 900),
    ('11000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000002', 1,
     'MATCH_INVOICE_PAYMENT', 'match_invoice_payment',
     'Test whether the large payment is supported by source records.',
     '{"invoice_id":"60000000-0000-0000-0000-000000000002"}',
     '{"match_id":"90000000-0000-0000-0000-000000000002","confidence":"HIGH"}',
     '{"source_ids":["60000000-0000-0000-0000-000000000002","70000000-0000-0000-0000-000000000005"]}',
     'CONTINUE', '2026-01-31T10:01:00Z', '2026-01-31T10:01:01Z', 1000),
    ('11000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000002', 2,
     'TEST_HYPOTHESIS', NULL,
     'The records corroborate a documented purchase and no suspicious onward flow.',
     '{}', '{"outcome":"REJECTED"}', '{"evidence_ids":["f0000000-0000-0000-0000-000000000005","f0000000-0000-0000-0000-000000000006"]}',
     'REJECT', '2026-01-31T10:01:01.100Z', '2026-01-31T10:01:02Z', 900);

INSERT INTO truelock.exposure_calculations (
    exposure_calculation_id, case_id, calculation_version, allocation_method, parameters
)
VALUES (
    '12000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'root-flow-v1',
    'FIFO_CONSERVATIVE',
    '{"max_depth":4,"max_horizon_days":30}'
);

INSERT INTO truelock.exposure_components (
    exposure_component_id, exposure_calculation_id, root_flow_id, component_type,
    source_record_type, source_record_id, root_bank_transaction_id,
    amount_mxn, occurred_at, path_sequence, allocation_details
)
VALUES
    ('13000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000001',
     'RF-001', 'ROOT', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000001',
     '70000000-0000-0000-0000-000000000001', 1000000, '2026-01-10T10:00:00-06:00', 0,
     '{"basis":"original company payment"}'),
    ('13000000-0000-0000-0000-000000000002', '12000000-0000-0000-0000-000000000001',
     'RF-001', 'DOWNSTREAM', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000002',
     '70000000-0000-0000-0000-000000000001', 920000, '2026-01-10T12:00:00-06:00', 1,
     '{"allocated_from_root":920000}'),
    ('13000000-0000-0000-0000-000000000003', '12000000-0000-0000-0000-000000000001',
     'RF-001', 'DOWNSTREAM', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000003',
     '70000000-0000-0000-0000-000000000001', 740000, '2026-01-10T14:00:00-06:00', 2,
     '{"allocated_from_root":740000}'),
    ('13000000-0000-0000-0000-000000000004', '12000000-0000-0000-0000-000000000001',
     'RF-001', 'RETURNED', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000004',
     '70000000-0000-0000-0000-000000000001', 740000, '2026-01-10T16:00:00-06:00', 3,
     '{"allocated_from_root":740000,"returned_to_origin":true}');

INSERT INTO truelock.findings (
    finding_id, case_id, thread_id, display_id, scheme_code, claim, status,
    confidence_label, exposure_calculation_id, supported_exposure_mxn,
    downstream_flow_mxn, coverage_sufficient
)
VALUES (
    '14000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'e0000000-0000-0000-0000-000000000001',
    'F001',
    'ROUND_TRIPPING',
    'The company paid MXN 1,000,000 to Proveedor Alfa; MXN 740,000 was traced through two intermediaries and returned to the originating company within six hours.',
    'SUPPORTED', 'HIGH', '12000000-0000-0000-0000-000000000001',
    1000000, 1660000, true
);

INSERT INTO truelock.finding_entities (finding_id, entity_id, role)
VALUES
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'ORIGIN'),
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', 'SUPPLIER'),
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000003', 'INTERMEDIARY'),
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000004', 'RETURN_SOURCE');

INSERT INTO truelock.finding_root_transactions (finding_id, bank_transaction_id, root_flow_id)
VALUES ('14000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', 'RF-001');

INSERT INTO truelock.finding_evidence (finding_id, evidence_id, role)
VALUES
    ('14000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000001', 'CONTEXTUAL'),
    ('14000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000002', 'SUPPORTING'),
    ('14000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000003', 'SUPPORTING'),
    ('14000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000004', 'SUPPORTING');

INSERT INTO truelock.case_file_versions (
    case_file_version_id, case_id, version_no, case_file
)
VALUES (
    '15000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    1,
    '{
      "case_id":"CASE-DEMO-001",
      "supported_exposure_mxn":1000000,
      "downstream_traced_mxn":1660000,
      "returned_mxn":740000,
      "net_supported_exposure_mxn":260000,
      "findings":["F001"],
      "rejected_leads":["L002"],
      "evidence_ids":["f0000000-0000-0000-0000-000000000001","f0000000-0000-0000-0000-000000000002","f0000000-0000-0000-0000-000000000003","f0000000-0000-0000-0000-000000000004"]
    }'::jsonb
);

COMMIT;
