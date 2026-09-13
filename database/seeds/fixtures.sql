- TrueLock demo fixtures.
-- Apply after all migrations.
--
-- The whole file runs inside a single transaction: if any statement fails,
-- nothing is committed and the database is left exactly as it was. Without
-- this, a failure midway through leaves entities/providers/accounts loaded
-- and invoices/payments/transactions empty, which looks like success on the
-- next run.
--
-- Idempotency: every statement can be re-applied. Note the deliberate
-- asymmetry in `providers` (see the comment on that statement): descriptive
-- columns are refreshed from this file, but an EFOS status already
-- discovered by the application is NOT reset back to 'UNKNOWN'.
--
-- WARNING about the data itself: these fixtures are not a neutral baseline.
-- They encode a capital round-tripping pattern on purpose (see the comment
-- above the `transactions` statement). Do not use this file as the clean
-- control case for regression tests.

BEGIN;

-- Optional: fail fast instead of hanging if another session holds locks.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';


-- ---------------------------------------------------------------------------
-- Entities
-- ---------------------------------------------------------------------------
-- `entity-provider` duplicates the RFC and name held in `providers` below.
-- Those two copies can drift and nothing in the schema prevents it. If this
-- becomes a problem, make `providers.rfc` a foreign key to `entities.rfc`
-- and drop the duplicated name.
INSERT INTO entities (id, rfc, name, entity_type)
VALUES
    ('entity-acme', 'AAA010101AAA', 'Acme Manufacturing, S.A. de C.V.', 'company'),
    ('entity-provider', 'PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', 'company'),
    ('entity-investigator', NULL, 'Maria Lopez', 'individual')
ON CONFLICT (id) DO UPDATE SET
    rfc = EXCLUDED.rfc,
    name = EXCLUDED.name,
    entity_type = EXCLUDED.entity_type;


-- ---------------------------------------------------------------------------
-- Providers
-- ---------------------------------------------------------------------------
-- `efos_status` and `efos_listed_date` are application state: the auditor
-- writes them when it verifies the SAT Article 69-B registry. Re-seeding them
-- unconditionally would silently erase the result of a demo run. They are
-- therefore only written when the existing row is still 'UNKNOWN'.
--
-- To force a hard reset to the pristine seed state, run instead:
--   UPDATE providers
--      SET efos_status = 'UNKNOWN', efos_listed_date = NULL
--    WHERE rfc = 'PRO010101PRO';
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
    efos_status = CASE
        WHEN providers.efos_status = 'UNKNOWN' THEN EXCLUDED.efos_status
        ELSE providers.efos_status
    END,
    efos_listed_date = CASE
        WHEN providers.efos_status = 'UNKNOWN' THEN EXCLUDED.efos_listed_date
        ELSE providers.efos_listed_date
    END;


-- ---------------------------------------------------------------------------
-- Accounts
-- ---------------------------------------------------------------------------
-- Note that entity-acme owns TWO accounts. That is what makes the
-- round-trip below detectable.
INSERT INTO accounts (account_no, entity_id, bank)
VALUES
    ('012345678901234567', 'entity-acme', 'Banco Demo'),
    ('987654321098765432', 'entity-provider', 'Banco Demo'),
    ('111122223333444455', 'entity-acme', 'Banco Demo')
ON CONFLICT (account_no) DO UPDATE SET
    entity_id = EXCLUDED.entity_id,
    bank = EXCLUDED.bank;


-- ---------------------------------------------------------------------------
-- Invoices
-- ---------------------------------------------------------------------------
-- FIXED: this statement previously declared 13 columns and supplied 12
-- values, so `cfdi_type` received 'Servicios de consultoria' and `concept`
-- received nothing. Postgres aborted with
--   ERROR: INSERT has more target columns than expressions
-- and the whole fixture load stopped here.
--
-- `cfdi_type` now carries 'I' (ingreso). In CFDI 4.0 this column takes a
-- letter - I, E, T, N or P - never a numeric code. '03' is a *forma de pago*
-- and belongs to `payment_form`, where it already is.
--
-- Amounts check out: 1000.00 subtotal + 160.00 IVA (16%) = 1160.00 total.
--
-- OPEN QUESTION - `payment_method = 'PUE'` combined with the `payments` row
-- below. If `payments` models CFDI complementos de pago (REP, type P), this
-- pairing cannot exist: complementos only apply to PPD invoices, and in PUE
-- the payment is implicit in the invoice itself. Either switch this to 'PPD',
-- or confirm that `payments` models bank settlement rather than a fiscal
-- receipt. Left as 'PUE' because changing it alters the meaning of the
-- fixture, which is your call and not a syntax fix.
INSERT INTO invoices (
    uuid, version, provider_rfc, receiver_rfc, issue_date, amount,
    subtotal, taxes, currency, payment_method, payment_form, cfdi_type, concept
)
VALUES (
    '11111111-1111-4111-8111-111111111111', '4.0', 'PRO010101PRO',
    'AAA010101AAA', DATE '2025-01-15', 1160.00, 1000.00, 160.00,
    'MXN', 'PUE', '03', 'I', 'Servicios de consultoria'
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


-- ---------------------------------------------------------------------------
-- Transactions
-- ---------------------------------------------------------------------------
-- Moved AHEAD of `payments` so that the IDs listed in
-- `payments.transaction_ids` already exist when that array is written.
-- `transactions.related_payment_id` is therefore seeded as NULL here and
-- back-filled after `payments` is inserted (see the UPDATE below). This is
-- the only way to load a mutual reference in one transaction without
-- deferrable constraints.
--
-- WHAT THIS DATA MEANS - read before using it as a control case:
--   transaction-demo-001  Acme       -> Proveedor   1160.00  2025-01-16
--   transaction-demo-002  Proveedor  -> Acme         900.00  2025-01-17
-- The second leg returns 900.00 of the 1160.00 to a DIFFERENT account owned
-- by the same payer, one day later, with no related payment and no invoice
-- backing it. Combined with an intangible consulting concept and an
-- unverified EFOS status, this is a textbook capital round-trip and the
-- auditor is expected to flag it. Intentional; not a data error.
INSERT INTO transactions (
    id, from_account, to_account, transaction_date, amount, related_payment_id
)
VALUES
    ('transaction-demo-001', '012345678901234567', '987654321098765432',
     DATE '2025-01-16', 1160.00, NULL),
    ('transaction-demo-002', '987654321098765432', '111122223333444455',
     DATE '2025-01-17', 900.00, NULL)
ON CONFLICT (id) DO UPDATE SET
    from_account = EXCLUDED.from_account,
    to_account = EXCLUDED.to_account,
    transaction_date = EXCLUDED.transaction_date,
    amount = EXCLUDED.amount;
    -- related_payment_id intentionally NOT reset here; it is set below.


-- ---------------------------------------------------------------------------
-- Payments
-- ---------------------------------------------------------------------------
-- Balances check out: 1160.00 previous - 1160.00 paid = 0.00 remaining.
--
-- CAVEAT - `transaction_ids` is a TEXT[]. Postgres cannot enforce a foreign
-- key on array elements, so nothing stops this column from holding IDs that
-- do not exist in `transactions`. The guard below turns that silent breakage
-- into a loud failure at load time, but it does not protect later writes. If
-- this relationship matters, replace the array with a `payment_transactions`
-- bridge table carrying real foreign keys in both directions.
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


-- Back-fill the transaction -> payment side of the mutual reference.
UPDATE transactions
   SET related_payment_id = 'payment-demo-001'
 WHERE id = 'transaction-demo-001'
   AND related_payment_id IS DISTINCT FROM 'payment-demo-001';


-- ---------------------------------------------------------------------------
-- Integrity guards
-- ---------------------------------------------------------------------------
-- These verify the things the schema cannot. Any failure aborts the whole
-- transaction, so a broken fixture never reaches a committed state.
--
-- Each check is scoped to the rows this file writes. That is deliberate: a
-- dev database full of unrelated junk should not block a fixture load. To
-- audit the entire database instead, drop the `WHERE ... IN (...)` scoping
-- clauses.
DO $$
DECLARE
    dangling  TEXT;
    bad_total NUMERIC;
BEGIN
    -- 1. Every ID in payments.transaction_ids must exist in transactions.
    SELECT string_agg(t.txid, ', ')
      INTO dangling
      FROM (
            SELECT DISTINCT unnest(p.transaction_ids) AS txid
              FROM payments p
             WHERE p.id IN ('payment-demo-001')
           ) t
     WHERE NOT EXISTS (SELECT 1 FROM transactions x WHERE x.id = t.txid);

    IF dangling IS NOT NULL THEN
        RAISE EXCEPTION
            'payments.transaction_ids references missing transactions: %',
            dangling;
    END IF;

    -- 2. Invoice totals must equal subtotal + taxes.
    SELECT string_agg(i.uuid::TEXT, ', ')
      INTO dangling
      FROM invoices i
     WHERE i.uuid IN ('11111111-1111-4111-8111-111111111111')
       AND i.amount <> i.subtotal + i.taxes;

    IF dangling IS NOT NULL THEN
        RAISE EXCEPTION 'invoice amount <> subtotal + taxes for: %', dangling;
    END IF;

    -- 3. Payment balances must be internally consistent.
    SELECT string_agg(p.id, ', ')
      INTO dangling
      FROM payments p
     WHERE p.id IN ('payment-demo-001')
       AND p.previous_balance - p.amount <> p.remaining_balance;

    IF dangling IS NOT NULL THEN
        RAISE EXCEPTION 'payment balances do not reconcile for: %', dangling;
    END IF;

    -- 4. A payment must not exceed the invoice it settles.
    SELECT string_agg(p.id, ', ')
      INTO dangling
      FROM payments p
      JOIN invoices i ON i.uuid = p.related_invoice_uuid
     WHERE p.id IN ('payment-demo-001')
       AND p.amount > i.amount;

    IF dangling IS NOT NULL THEN
        RAISE EXCEPTION 'payment exceeds its invoice for: %', dangling;
    END IF;

    -- 5. Sanity: the fixtures must have loaded completely.
    SELECT count(*) INTO bad_total FROM transactions
     WHERE id IN ('transaction-demo-001', 'transaction-demo-002');
    IF bad_total <> 2 THEN
        RAISE EXCEPTION 'expected 2 demo transactions, found %', bad_total;
    END IF;
END
$$;

COMMIT;
