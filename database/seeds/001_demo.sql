-- TrueLock demo fixtures.
-- Apply after all migrations. Every statement is idempotent so this file
-- can be used repeatedly against a development database.

INSERT INTO entities (id, rfc, name, entity_type)
VALUES
    ('entity-acme', 'AAA010101AAA', 'Acme Manufacturing, S.A. de C.V.', 'company'),
    ('entity-provider', 'PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', 'company'),
    ('entity-investigator', NULL, 'Maria Lopez', 'individual')
ON CONFLICT (id) DO UPDATE SET
    rfc = EXCLUDED.rfc,
    name = EXCLUDED.name,
    entity_type = EXCLUDED.entity_type;

INSERT INTO providers (
    rfc, name, registration_date, address, phone, efos_status, efos_listed_date
)
VALUES (
    'PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', DATE '2018-03-15',
    'Av. Reforma 100, Ciudad de México', '+52-55-5555-0101',
    'UNKNOWN', NULL
)
ON CONFLICT (rfc) DO UPDATE SET
    name = EXCLUDED.name,
    registration_date = EXCLUDED.registration_date,
    address = EXCLUDED.address,
    phone = EXCLUDED.phone,
    efos_status = EXCLUDED.efos_status,
    efos_listed_date = EXCLUDED.efos_listed_date;

INSERT INTO accounts (account_no, entity_id, bank)
VALUES
    ('012345678901234567', 'entity-acme', 'Banco Demo'),
    ('987654321098765432', 'entity-provider', 'Banco Demo'),
    ('111122223333444455', 'entity-acme', 'Banco Demo')
ON CONFLICT (account_no) DO UPDATE SET
    entity_id = EXCLUDED.entity_id,
    bank = EXCLUDED.bank;

INSERT INTO invoices (
    uuid, version, provider_rfc, receiver_rfc, issue_date, amount,
    subtotal, taxes, currency, payment_method, payment_form, cfdi_type, concept
)
VALUES (
    '11111111-1111-4111-8111-111111111111', '4.0', 'PRO010101PRO',
    'AAA010101AAA', DATE '2025-01-15', 1160.00, 1000.00, 160.00,
    'MXN', 'PUE', '03', 'Servicios de consultoria'
)
ON CONFLICT (uuid) DO UPDATE SET
    version = EXCLUDED.version,
    provider_rfc = EXCLUDED.provider_rfc,
    receiver_rfc = EXCLUDED.receiver_rfc,
    issue_date = EXCLUDED.issue_date,
    amount = EXCLUDED.amount,
    subtotal = EXCLUDED.subtotal,
    taxes = EXCLUDED.taxes,
    currency = EXCLUDED.currency,
    payment_method = EXCLUDED.payment_method,
    payment_form = EXCLUDED.payment_form,
    cfdi_type = EXCLUDED.cfdi_type,
    concept = EXCLUDED.concept;

INSERT INTO payments (
    id, related_invoice_uuid, payment_date, amount, payment_form, currency,
    previous_balance, remaining_balance, transaction_ids
)
VALUES (
    'payment-demo-001', '11111111-1111-4111-8111-111111111111',
    DATE '2025-01-16', 1160.00, '03', 'MXN', 1160.00, 0.00,
    ARRAY['transaction-demo-001']::TEXT[]
)
ON CONFLICT (id) DO UPDATE SET
    related_invoice_uuid = EXCLUDED.related_invoice_uuid,
    payment_date = EXCLUDED.payment_date,
    amount = EXCLUDED.amount,
    payment_form = EXCLUDED.payment_form,
    currency = EXCLUDED.currency,
    previous_balance = EXCLUDED.previous_balance,
    remaining_balance = EXCLUDED.remaining_balance,
    transaction_ids = EXCLUDED.transaction_ids;

INSERT INTO transactions (
    id, from_account, to_account, transaction_date, amount, related_payment_id
)
VALUES
    ('transaction-demo-001', '012345678901234567', '987654321098765432',
     DATE '2025-01-16', 1160.00, 'payment-demo-001'),
    ('transaction-demo-002', '987654321098765432', '111122223333444455',
     DATE '2025-01-17', 900.00, NULL)
ON CONFLICT (id) DO UPDATE SET
    from_account = EXCLUDED.from_account,
    to_account = EXCLUDED.to_account,
    transaction_date = EXCLUDED.transaction_date,
    amount = EXCLUDED.amount,
    related_payment_id = EXCLUDED.related_payment_id;
