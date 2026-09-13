-- TrueLock demo fixtures: clean control case.
-- Source data: the "Normal Supplier" scenario in the-forensic-auditor
-- (agent/tools/mock_tools.ts -> SCENARIO_RFCS.NORMAL / REC-NORM-*).
--
-- Unlike fixtures.sql, nothing here is meant to look suspicious: one
-- provider with real IMSS-registered employees, one invoice, one
-- payment that fully settles it, one transaction that matches the
-- payment exactly. Use this as the neutral baseline; use fixtures.sql
-- for the round-trip fraud pattern.
--
-- Whole file runs in one transaction, and every INSERT is safe to
-- re-run (ON CONFLICT DO NOTHING).

BEGIN;

-- Entities: the supplier and the receiver (Pemex, per the mock data).
INSERT INTO entities (id, rfc, name, entity_type)
VALUES
    ('entity-normal-supplier', 'NORM850101AB1', 'Industrias Manufactureras Normales, S.A. de C.V.', 'company'),
    ('entity-pemex', 'PEMX800101001', 'Petroleos Mexicanos', 'company')
ON CONFLICT (id) DO NOTHING;

-- Provider profile. EFOS status starts UNKNOWN, same as a fresh seed
-- in fixtures.sql; there's no round-tripping logic to protect here.
INSERT INTO providers (
    rfc, name, registration_date, address, phone, efos_status, efos_listed_date
)
VALUES (
    'NORM850101AB1', 'Industrias Manufactureras Normales, S.A. de C.V.',
    DATE '2008-04-12', 'Av. Industrial 450, Parque Industrial, Monterrey, NL',
    '+52-81-5555-0185', 'UNKNOWN', NULL
)
ON CONFLICT (rfc) DO NOTHING;

-- One account per entity, enough to carry a single payment.
INSERT INTO accounts (account_no, entity_id, bank)
VALUES
    ('444455556666777788', 'entity-normal-supplier', 'Banco Demo'),
    ('999988887777666655', 'entity-pemex', 'Banco Demo')
ON CONFLICT (account_no) DO NOTHING;

-- Invoice: 1,200,000.00 subtotal + 192,000.00 IVA (16%) = 1,392,000.00.
INSERT INTO invoices (
    uuid, version, provider_rfc, receiver_rfc, issue_date, amount,
    subtotal, taxes, currency, payment_method, payment_form, cfdi_type, concept
)
VALUES (
    '22222222-2222-4222-8222-222222222222', '4.0', 'NORM850101AB1',
    'PEMX800101001', DATE '2024-03-10', 1392000.00, 1200000.00, 192000.00,
    'MXN', 'PUE', '03', 'I', 'Suministro de tuberia de acero estructural certificada'
)
ON CONFLICT (uuid) DO NOTHING;

-- Single SPEI transfer settling the invoice in full, same day pattern
-- as the mock data (payer -> supplier, no second leg).
INSERT INTO transactions (
    id, from_account, to_account, transaction_date, amount, related_payment_id
)
VALUES (
    'transaction-normal-001', '999988887777666655', '444455556666777788',
    DATE '2024-03-12', 1392000.00, NULL
)
ON CONFLICT (id) DO NOTHING;

-- Payment: fully reconciled, previous balance equals the amount paid.
INSERT INTO payments (
    id, related_invoice_uuid, payment_date, amount, payment_form, currency,
    previous_balance, remaining_balance, transaction_ids
)
VALUES (
    'payment-normal-001', '22222222-2222-4222-8222-222222222222',
    DATE '2024-03-12', 1392000.00, '03', 'MXN', 1392000.00, 0.00,
    ARRAY['transaction-normal-001']::TEXT[]
)
ON CONFLICT (id) DO NOTHING;

UPDATE transactions
   SET related_payment_id = 'payment-normal-001'
 WHERE id = 'transaction-normal-001'
   AND related_payment_id IS DISTINCT FROM 'payment-normal-001';

COMMIT;
