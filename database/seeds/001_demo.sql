BEGIN;

-- Canonical demo aligned with backend/src/truelock/seeder/demo_scenario.py
-- Cycle: $1,000,000 -> $920,000 -> $740,000 return; plus legitimate shared-address control.

INSERT INTO truelock.organizations (organization_id, legal_name, rfc)
VALUES ('00000000-0000-0000-0000-000000000001', 'Empresa Operadora Nacional SA de CV', 'EDE180101AA1');

INSERT INTO truelock.cases (
    case_id, organization_id, display_id, title, status, base_currency, metadata
)
VALUES (
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'CASE-DEMO-001',
    'Round-trip with legitimate control suppliers',
    'COMPLETED',
    'MXN',
    '{"fixture":"canonical-demo-v2","source":"demo_scenario.py","expected_supported_findings":1,"expected_rejected_leads":1}'
);

INSERT INTO truelock.source_files (
    source_file_id, case_id, original_filename, dataset_kind, media_type,
    byte_size, sha256, parser_name, parser_version, status, record_count, ingested_at
)
VALUES
    ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'suppliers.csv', 'SUPPLIER_MASTER', 'text/csv', 1000, repeat('1',64),
     'supplier_csv', '1.0.0', 'IMPORTED', 4, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'invoices.xml', 'CFDI_INVOICE', 'application/xml', 2000, repeat('2',64),
     'cfdi_4_xml', '1.0.0', 'IMPORTED', 1, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'bank.csv', 'BANK', 'text/csv', 3000, repeat('3',64),
     'bank_csv', '1.0.0', 'IMPORTED', 5, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'ledger.csv', 'LEDGER', 'text/csv', 3000, repeat('4',64),
     'ledger_csv', '1.0.0', 'IMPORTED', 4, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     'efos_69b.csv', 'SAT_69B', 'text/csv', 500, repeat('5',64),
     'efos_69b_csv', '1.0.0', 'IMPORTED', 1, clock_timestamp()),
    ('20000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000001',
     'payments.xml', 'CFDI_PAYMENT', 'application/xml', 800, repeat('6',64),
     'cfdi_payment', '1.0.0', 'IMPORTED', 1, clock_timestamp());

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
    '2026-08-01T00:00:00-06:00'::timestamptz,
    '2026-08-31T23:59:59-06:00'::timestamptz,
    true,
    'Synthetic fixture declares complete August coverage',
    'America/Mexico_City',
    CASE WHEN dataset_kind = 'BANK' THEN 'SEPARATE_DIRECTION' ELSE NULL END
FROM truelock.source_files
WHERE case_id = '10000000-0000-0000-0000-000000000001';

INSERT INTO truelock.entities (
    entity_id, case_id, entity_type, canonical_name, legal_name, rfc,
    source_file_id, source_locator, raw_payload
)
VALUES
    ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'COMPANY', 'Empresa Operadora Nacional SA de CV', 'Empresa Operadora Nacional SA de CV', 'EDE180101AA1',
     '20000000-0000-0000-0000-000000000001', 'entity:ENT-COMPANY-001',
     '{"external_entity_id":"ENT-COMPANY-001"}'::jsonb),
    ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'SUPPLIER', 'Constructora e Infraestructura Primaria SA de CV',
     'Constructora e Infraestructura Primaria SA de CV', 'CPR190515BB2',
     '20000000-0000-0000-0000-000000000001', 'entity:ENT-VENDOR-001',
     '{"external_entity_id":"ENT-VENDOR-001"}'::jsonb),
    ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'UNKNOWN', 'Logística y Enlaces Rápidos Fantasma SA de CV',
     'Logística y Enlaces Rápidos Fantasma SA de CV', 'LSF200820CC3',
     '20000000-0000-0000-0000-000000000001', 'entity:ENT-SHELL-001',
     '{"external_entity_id":"ENT-SHELL-001"}'::jsonb),
    ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'SUPPLIER', 'Papelería Corporativa Reforma SA', 'Papelería Corporativa Reforma SA', 'PCR150310AA1',
     '20000000-0000-0000-0000-000000000001', 'entity:ENT-VENDOR-CONTROL-A',
     '{"external_entity_id":"ENT-VENDOR-CONTROL-A"}'::jsonb),
    ('30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     'SUPPLIER', 'Consultoría Reforma Legal SC', 'Consultoría Reforma Legal SC', 'CRL170822BB2',
     '20000000-0000-0000-0000-000000000001', 'entity:ENT-VENDOR-CONTROL-B',
     '{"external_entity_id":"ENT-VENDOR-CONTROL-B"}'::jsonb);

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
     repeat('a',64), '012180000000000001', '**************0001', 'BBVA', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     repeat('b',64), '012180000000000002', '**************0002', 'BBVA', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     repeat('c',64), '012180000000000003', '**************0003', 'Banorte', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     repeat('d',64), '012180000000000004', '**************0004', 'Santander', 'MXN',
     '20000000-0000-0000-0000-000000000003'),
    ('40000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     repeat('e',64), '012180000000000005', '**************0005', 'Citibanamex', 'MXN',
     '20000000-0000-0000-0000-000000000003');

INSERT INTO truelock.entity_bank_accounts (entity_id, bank_account_id, is_primary, source_file_id, source_locator)
VALUES
    ('30000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', true,
     '20000000-0000-0000-0000-000000000003', 'account:1'),
    ('30000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000002', true,
     '20000000-0000-0000-0000-000000000001', 'account:2'),
    ('30000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000003', true,
     '20000000-0000-0000-0000-000000000003', 'account:3'),
    ('30000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000004', true,
     '20000000-0000-0000-0000-000000000001', 'account:4'),
    ('30000000-0000-0000-0000-000000000005', '40000000-0000-0000-0000-000000000005', true,
     '20000000-0000-0000-0000-000000000001', 'account:5');

INSERT INTO truelock.suppliers (
    supplier_id, case_id, entity_id, external_supplier_id, legal_name, rfc,
    address_raw, address_normalized, created_at_source, category,
    source_file_id, source_locator, record_sha256
)
VALUES
    ('50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000002', 'SUP-VENDOR-001',
     'Constructora e Infraestructura Primaria SA de CV', 'CPR190515BB2',
     'Av. Insurgentes Sur 1602, CDMX', 'AV INSURGENTES SUR 1602 CDMX',
     '2026-07-01T10:00:00-06:00', 'CONSTRUCTION',
     '20000000-0000-0000-0000-000000000001', 'row:2', repeat('51',32)),
    ('50000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000003', 'SUP-SHELL-001',
     'Logística y Enlaces Rápidos Fantasma SA de CV', 'LSF200820CC3',
     'Calle Falsa 123, Bodega 4', 'CALLE FALSA 123 BODEGA 4',
     '2026-07-15T10:00:00-06:00', 'LOGISTICS',
     '20000000-0000-0000-0000-000000000001', 'row:3', repeat('52',32)),
    ('50000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000004', 'SUP-CONTROL-A',
     'Papelería Corporativa Reforma SA', 'PCR150310AA1',
     'Av. Reforma 222, Piso 4, CDMX', 'AV REFORMA 222 PISO 4 CDMX',
     '2025-01-10T10:00:00-06:00', 'SUPPLIES',
     '20000000-0000-0000-0000-000000000001', 'row:4', repeat('53',32)),
    ('50000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000005', 'SUP-CONTROL-B',
     'Consultoría Reforma Legal SC', 'CRL170822BB2',
     'Av. Reforma 222, Piso 4, CDMX', 'AV REFORMA 222 PISO 4 CDMX',
     '2025-03-12T10:00:00-06:00', 'LEGAL',
     '20000000-0000-0000-0000-000000000001', 'row:5', repeat('54',32));

INSERT INTO truelock.sat_69b_snapshots (
    sat_snapshot_id, source_file_id, snapshot_date, source_url, publication_reference
)
VALUES (
    '21000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000005',
    '2025-11-10',
    'https://example.sat.gob.mx/69b',
    'canonical-demo-efos'
);

INSERT INTO truelock.sat_69b_records (
    sat_record_id, sat_snapshot_id, rfc, legal_name, status,
    source_publication_date, source_locator, raw_row_json
)
VALUES (
    '22000000-0000-0000-0000-000000000001',
    '21000000-0000-0000-0000-000000000001',
    'LSF200820CC3',
    'Logística y Enlaces Rápidos Fantasma SA de CV',
    'DEFINITIVO',
    '2025-11-10',
    'row:2',
    '{"rfc":"LSF200820CC3","status":"DEFINITIVO","contextual_only":true}'::jsonb
);

INSERT INTO truelock.invoices (
    invoice_id, case_id, source_file_id, source_locator, record_sha256,
    uuid, version, issue_timestamp, issuer_entity_id, receiver_entity_id,
    rfc_issuer, issuer_name, rfc_receiver, receiver_name, subtotal, tax_total,
    total, currency, amount_mxn, cfdi_type, payment_method, payment_form, cfdi_status,
    raw_xml_sha256
)
VALUES
    ('60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000002', 'xml:invoice:1', repeat('7',64),
     '11111111-2222-3333-4444-555555555555', '4.0', '2026-08-01T08:00:00-06:00',
     '30000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000001',
     'CPR190515BB2', 'Constructora e Infraestructura Primaria SA de CV',
     'EDE180101AA1', 'Empresa Operadora Nacional SA de CV',
     862068.965517, 137931.034483, 1000000, 'MXN', 1000000, 'I', 'PUE', '03', 'ACTIVE', repeat('8',64));

INSERT INTO truelock.invoice_concepts (
    invoice_id, line_no, product_service_code, quantity, description, unit_value, amount
)
VALUES
    ('60000000-0000-0000-0000-000000000001', 1, '72121500', 1,
     'Infraestructura y obra civil', 862068.965517, 862068.965517);

INSERT INTO truelock.payment_complements (
    payment_id, case_id, source_file_id, source_locator, payment_cfdi_uuid,
    payment_date, currency, payment_form, payment_amount, amount_mxn,
    operation_number, external_payment_id, record_sha256, raw_payload
)
VALUES (
    '61000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000006',
    'xml:payment:1',
    '11111111-2222-3333-4444-555555555555',
    '2026-08-02T10:00:00-06:00',
    'MXN',
    '03',
    1000000,
    1000000,
    'PMT-ROOT-001',
    'PMT-ROOT-001',
    repeat('61',32),
    '{"external_payment_id":"PMT-ROOT-001"}'::jsonb
);

INSERT INTO truelock.payment_documents (
    payment_document_id, payment_id, invoice_id, related_document_uuid,
    document_currency, installment_no, previous_balance, amount_paid, remaining_balance
)
VALUES (
    '62000000-0000-0000-0000-000000000001',
    '61000000-0000-0000-0000-000000000001',
    '60000000-0000-0000-0000-000000000001',
    '11111111-2222-3333-4444-555555555555',
    'MXN', 1, 1000000, 1000000, 0
);

INSERT INTO truelock.bank_transactions (
    bank_transaction_id, case_id, source_file_id, source_locator,
    external_transaction_id, related_payment_external_id, observed_bank_account_id,
    booked_at, value_date, direction, origin_bank_account_id, destination_bank_account_id,
    origin_entity_id, destination_entity_id, amount, currency, amount_mxn,
    reference, concept, record_sha256
)
VALUES
    ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:2', 'TX-ROOT-001', 'PMT-ROOT-001',
     '40000000-0000-0000-0000-000000000001', '2026-08-02T10:00:00-06:00', '2026-08-02', 'DEBIT',
     '40000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000002',
     '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002',
     1000000, 'MXN', 1000000, '11111111-2222-3333-4444-555555555555', 'Invoice payment', repeat('a1',32)),
    ('70000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:3', 'TX-HOP-001', NULL,
     '40000000-0000-0000-0000-000000000002', '2026-08-02T12:00:00-06:00', '2026-08-02', 'DEBIT',
     '40000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000003',
     '30000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000003',
     920000, 'MXN', 920000, 'TRANSFER-VENDOR-SHELL', 'Rapid pass-through', repeat('b1',32)),
    ('70000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:4', 'TX-RET-001', NULL,
     '40000000-0000-0000-0000-000000000003', '2026-08-03T09:00:00-06:00', '2026-08-03', 'CREDIT',
     '40000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000001',
     740000, 'MXN', 740000, 'TRANSFER-SHELL-COMPANY', 'Circular return', repeat('c1',32)),
    ('70000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:5', 'TX-LEGIT-001', NULL,
     '40000000-0000-0000-0000-000000000001', '2026-08-04T10:00:00-06:00', '2026-08-04', 'DEBIT',
     '40000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000004',
     '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000004',
     15420, 'MXN', 15420, 'SUPPLIES-PCR', 'Office supplies', repeat('d1',32)),
    ('70000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000003', 'row:6', 'TX-LEGIT-002', NULL,
     '40000000-0000-0000-0000-000000000001', '2026-08-05T10:00:00-06:00', '2026-08-05', 'DEBIT',
     '40000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000005',
     '30000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000005',
     38500, 'MXN', 38500, 'LEGAL-CRL', 'Legal advisory', repeat('e1',32));

INSERT INTO truelock.ledger_entries (
    journal_line_id, case_id, source_file_id, source_locator, journal_entry_id,
    posting_date, account_code, account_name, account_type, debit, credit,
    currency, base_amount_mxn, supplier_id, invoice_id, invoice_uuid, description
)
VALUES
    ('80000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:2', 'JE-001', '2026-08-01', '6100', 'Construction expense', 'EXPENSE', 1000000, 0, 'MXN', 1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '11111111-2222-3333-4444-555555555555', 'Book vendor invoice'),
    ('80000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:3', 'JE-001', '2026-08-01', '2100', 'Accounts payable', 'LIABILITY', 0, 1000000, 'MXN', -1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '11111111-2222-3333-4444-555555555555', 'Book vendor invoice'),
    ('80000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:4', 'JE-002', '2026-08-02', '2100', 'Accounts payable', 'LIABILITY', 1000000, 0, 'MXN', 1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '11111111-2222-3333-4444-555555555555', 'Settle vendor invoice'),
    ('80000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004', 'row:5', 'JE-002', '2026-08-02', '1100', 'Cash', 'ASSET', 0, 1000000, 'MXN', -1000000, '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '11111111-2222-3333-4444-555555555555', 'Settle vendor invoice');

INSERT INTO truelock.reconciliation_matches (
    reconciliation_match_id, case_id, match_type, status, confidence,
    matched_amount, currency, amount_mxn, rules, explanation, created_by
)
VALUES
    ('90000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'UUID_AMOUNT_SUPPLIER_TIME', 'CONFIRMED', 'HIGH', 1000000, 'MXN', 1000000,
     '["UUID_EXACT","AMOUNT_EXACT","SUPPLIER_EXACT","TIME_DELTA_2H"]',
     'Invoice UUID appears in bank reference and amount and supplier match.', 'seed-reconciler-v2');

INSERT INTO truelock.reconciliation_invoice_allocations (reconciliation_match_id, invoice_id, allocated_amount)
VALUES ('90000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 1000000);

INSERT INTO truelock.reconciliation_bank_allocations (reconciliation_match_id, bank_transaction_id, allocated_amount)
VALUES ('90000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', 1000000);

INSERT INTO truelock.detector_runs (
    detector_run_id, case_id, detector_code, detector_version, parameters,
    status, started_at, finished_at, records_scanned, anomalies_emitted
)
VALUES
    ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'RAPID_PASS_THROUGH', '1.0.0', '{"ratio":0.8,"window_hours":24}',
     'COMPLETED', '2026-08-02T11:00:00Z', '2026-08-02T11:00:01Z', 5, 1),
    ('a0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'CYCLE', '1.0.0', '{"max_depth":4,"window_days":30}',
     'COMPLETED', '2026-08-03T09:00:00Z', '2026-08-03T09:00:01Z', 5, 1),
    ('a0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'SHARED_ADDRESS_CONTROL', '1.0.0', '{"require_economic_link":true}',
     'COMPLETED', '2026-08-04T10:00:00Z', '2026-08-04T10:00:01Z', 2, 1);

INSERT INTO truelock.anomalies (
    anomaly_id, case_id, detector_run_id, detector_code, status,
    title, description, strength, amount_mxn, occurred_at, details
)
VALUES
    ('b0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000001', 'RAPID_PASS_THROUGH', 'GROUPED_INTO_LEAD',
     '92% moved within two hours', 'Constructora Primaria moved MXN 920,000 shortly after receipt.',
     0.92, 920000, '2026-08-02T12:00:00-06:00', '{"ratio":0.92,"elapsed_hours":2}'),
    ('b0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000002', 'CYCLE', 'GROUPED_INTO_LEAD',
     'Time-respecting three-edge cycle', 'Funds returned to the originating company within one day.',
     0.95, 740000, '2026-08-03T09:00:00-06:00', '{"depth":3,"returned_amount_mxn":740000}'),
    ('b0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000003', 'SHARED_ADDRESS_CONTROL', 'GROUPED_INTO_LEAD',
     'Shared commercial address control', 'Two independent Reforma suppliers share an address without inter-transfer.',
     0.20, 0, '2026-08-04T10:00:00-06:00', '{"address":"Av. Reforma 222"}');

INSERT INTO truelock.anomaly_records (anomaly_id, record_type, record_id, role, source_file_id, source_locator)
VALUES
    ('b0000000-0000-0000-0000-000000000001', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000001', 'INFLOW', '20000000-0000-0000-0000-000000000003', 'row:2'),
    ('b0000000-0000-0000-0000-000000000001', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000002', 'OUTFLOW', '20000000-0000-0000-0000-000000000003', 'row:3'),
    ('b0000000-0000-0000-0000-000000000002', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000003', 'RETURN', '20000000-0000-0000-0000-000000000003', 'row:4'),
    ('b0000000-0000-0000-0000-000000000003', 'ENTITY', '30000000-0000-0000-0000-000000000004', 'CONTROL_A', '20000000-0000-0000-0000-000000000001', 'row:4');

INSERT INTO truelock.leads (
    lead_id, case_id, display_id, external_lead_key, title, risk_score, risk_score_version,
    priority, status, reason_summary
)
VALUES
    ('c0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'L001', 'LEAD-CYCLE-TX-ROOT-001', 'Constructora Primaria round-trip', 92, 'demo-v2', 'CRITICAL', 'SUPPORTED',
     'Independent rapid-pass-through and cycle signals justify investigation.'),
    ('c0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'L002', 'LEAD-CONTROL-SHARED-ADDRESS', 'Shared Reforma address control', 20, 'demo-v2', 'LOW', 'REJECTED',
     'Shared commercial address alone is not economic linkage; no inter-transfer exists.');

INSERT INTO truelock.lead_anomalies (lead_id, anomaly_id)
VALUES
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002'),
    ('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003');

INSERT INTO truelock.lead_entities (lead_id, entity_id, role)
VALUES
    ('c0000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', 'SUBJECT'),
    ('c0000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000004', 'SUBJECT');

INSERT INTO truelock.investigations (
    investigation_id, case_id, lead_id, status, model_provider, model_name,
    tool_calls_used, started_at, completed_at, idempotency_key, dataset_fingerprint
)
VALUES
    ('d0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'c0000000-0000-0000-0000-000000000001', 'COMPLETED', 'fixture', 'deterministic-seed',
     3, '2026-08-31T10:00:00Z', '2026-08-31T10:00:03Z',
     'seed:LEAD-CYCLE-TX-ROOT-001', NULL),
    ('d0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'c0000000-0000-0000-0000-000000000002', 'COMPLETED', 'fixture', 'deterministic-seed',
     1, '2026-08-31T10:01:00Z', '2026-08-31T10:01:01Z',
     'seed:LEAD-CONTROL-SHARED-ADDRESS', NULL);

INSERT INTO truelock.investigation_threads (
    thread_id, investigation_id, case_id, display_id, scheme_code,
    hypothesis_claim, status, tool_calls_used, last_new_evidence_sequence,
    outcome_reason, created_at, closed_at
)
VALUES
    ('e0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000001', 'T001', 'ROUND_TRIPPING',
     'Constructora Primaria may be a pass-through in a time-respecting round trip.',
     'SUPPORTED', 3, 3, 'The bank path returns MXN 740,000 to the originating company.',
     '2026-08-31T10:00:00Z', '2026-08-31T10:00:03Z'),
    ('e0000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000002',
     '10000000-0000-0000-0000-000000000001', 'T002', 'SHARED_ADDRESS',
     'Shared Reforma address may indicate related-party fraud.',
     'REJECTED', 1, 1,
     'Distinct RFCs, accounts, and no inter-transfer; address alone is not sufficient.',
     '2026-08-31T10:01:00Z', '2026-08-31T10:01:01Z');

INSERT INTO truelock.evidence (
    evidence_id, case_id, evidence_type, record_id, source_file_id,
    source_locator, source_record_sha256, facts, created_by
)
VALUES
    ('f0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'INVOICE', '60000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
     'xml:invoice:1', repeat('7',64), '{"uuid":"11111111-2222-3333-4444-555555555555","total_mxn":1000000}', 'get_invoice'),
    ('f0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000003',
     'row:2', repeat('a1',32), '{"amount_mxn":1000000,"timestamp":"2026-08-02T10:00:00-06:00","role":"ROOT","external_id":"TX-ROOT-001"}', 'trace_money'),
    ('f0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000003',
     'row:3', repeat('b1',32), '{"amount_mxn":920000,"elapsed_hours":2,"role":"DOWNSTREAM","external_id":"TX-HOP-001"}', 'trace_money'),
    ('f0000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000003',
     'row:4', repeat('c1',32), '{"amount_mxn":740000,"role":"RETURNED","external_id":"TX-RET-001"}', 'trace_money'),
    ('f0000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001',
     'SAT_69B_RECORD', '22000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000005',
     'row:2', NULL, '{"rfc":"LSF200820CC3","status":"DEFINITIVO","role":"CIRCUMSTANTIAL"}', 'check_efos_status');

INSERT INTO truelock.thread_evidence (thread_id, evidence_id, role, assertion_code)
VALUES
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000001', 'CONTEXTUAL', 'ROOT_INVOICE'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000002', 'SUPPORTING', 'ROOT_PAYMENT'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000003', 'SUPPORTING', 'RAPID_OUTFLOW'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000004', 'SUPPORTING', 'RETURN_TO_ORIGIN'),
    ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000005', 'CONTEXTUAL', 'EFOS_SHELL');

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
     '{"invoice_uuid":"11111111-2222-3333-4444-555555555555"}',
     '{"payment_id":"PMT-ROOT-001","confidence":"HIGH"}',
     '{"source_ids":["11111111-2222-3333-4444-555555555555","TX-ROOT-001"]}',
     'CONTINUE', '2026-08-31T10:00:00Z', '2026-08-31T10:00:00.400Z', 400),
    ('11000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 2,
     'TRACE_MONEY', 'trace_money',
     'The supplier moved 92% of the root payment within two hours.',
     '{"start_transaction_id":"TX-ROOT-001","max_hops":4}',
     '{"path_transaction_ids":["TX-ROOT-001","TX-HOP-001","TX-RET-001"]}',
     '{"source_file_id":"20000000-0000-0000-0000-000000000003"}',
     'CONTINUE', '2026-08-31T10:00:00.500Z', '2026-08-31T10:00:02Z', 1500),
    ('11000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 3,
     'TEST_HYPOTHESIS', NULL,
     'The time-respecting path returns supported funds to the originating company.',
     '{}', '{"outcome":"SUPPORTED"}',
     '{"evidence_ids":["f0000000-0000-0000-0000-000000000002","f0000000-0000-0000-0000-000000000004"]}',
     'SUPPORT', '2026-08-31T10:00:02.100Z', '2026-08-31T10:00:03Z', 900),
    ('11000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000002', 1,
     'TEST_HYPOTHESIS', NULL,
     'Shared address without economic linkage does not substantiate fraud.',
     '{}', '{"outcome":"REJECTED"}', '{}',
     'REJECT', '2026-08-31T10:01:00Z', '2026-08-31T10:01:01Z', 1000);

INSERT INTO truelock.exposure_calculations (
    exposure_calculation_id, case_id, calculation_version, allocation_method, parameters
)
VALUES (
    '12000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'root-flow-v1',
    'ROOT_FLOW_UNDUPLICATED_WITH_RETURN_OFFSET',
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
     '70000000-0000-0000-0000-000000000001', 1000000, '2026-08-02T10:00:00-06:00', 0,
     '{"basis":"original company payment","external_id":"TX-ROOT-001"}'),
    ('13000000-0000-0000-0000-000000000002', '12000000-0000-0000-0000-000000000001',
     'RF-001', 'DOWNSTREAM', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000002',
     '70000000-0000-0000-0000-000000000001', 920000, '2026-08-02T12:00:00-06:00', 1,
     '{"allocated_from_root":920000,"external_id":"TX-HOP-001"}'),
    ('13000000-0000-0000-0000-000000000003', '12000000-0000-0000-0000-000000000001',
     'RF-001', 'RETURNED', 'BANK_TRANSACTION', '70000000-0000-0000-0000-000000000003',
     '70000000-0000-0000-0000-000000000001', 740000, '2026-08-03T09:00:00-06:00', 2,
     '{"allocated_from_root":740000,"returned_to_origin":true,"external_id":"TX-RET-001"}');

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
    'The company paid MXN 1,000,000 to Constructora Primaria; MXN 740,000 was traced through an intermediary and returned to the originating company.',
    'SUPPORTED', 'HIGH', '12000000-0000-0000-0000-000000000001',
    1000000, 920000, true
);

INSERT INTO truelock.finding_entities (finding_id, entity_id, role)
VALUES
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'ORIGIN'),
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', 'SUPPLIER'),
    ('14000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000003', 'INTERMEDIARY');

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
      "downstream_traced_mxn":920000,
      "returned_mxn":740000,
      "net_supported_exposure_mxn":260000,
      "findings":["F001"],
      "rejected_leads":["L002"],
      "cycle":["TX-ROOT-001","TX-HOP-001","TX-RET-001"],
      "evidence_ids":["f0000000-0000-0000-0000-000000000001","f0000000-0000-0000-0000-000000000002","f0000000-0000-0000-0000-000000000003","f0000000-0000-0000-0000-000000000004"]
    }'::jsonb
);

COMMIT;
