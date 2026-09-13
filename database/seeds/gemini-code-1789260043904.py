import psycopg2
from psycopg2 import sql
 
class TrueLockSeeder:
    """
    Seeds TrueLock with one clean control case and three fraud cases:
 
      1. Round-trip capital (Acme <-> Proveedor Ejemplo)
         Signals: intangible invoice concept, unverified EFOS status,
         two accounts on the same payer entity, next-day partial return
         to the second account with no invoice/payment backing it.
 
      2. EFOS-blacklisted issuer with diverted payment
         (Comercializadora EFOS del Sur -> Gobierno Estatal Ejemplo)
         Signals: provider already DEFINITIVO on the SAT 69-B registry
         (not just unverified - actually confirmed), an intangible,
         inflated invoice concept, PPD payment method (deferred, so a
         later complemento de pago makes sense - unlike fraud case 1,
         which left this inconsistent), and the settling transaction
         landing in an account that belongs to neither the invoicing
         provider nor a documented intermediary.
 
      3. Fan-in structuring via freshly incorporated shells
         (Servicios Fantasma Alpha/Beta/Gamma -> Consultoria Acumuladora)
         Signals: three suppliers incorporated days apart under a
         sequential RFC pattern, each issuing/receiving a
         word-for-word identical "consulting" invoice concept, all
         settling into the same collector account within a two-day
         window - individually reconciled, only suspicious in
         aggregate.
 
      Control case: Pemex <-> Industrias Manufactureras Normales
         Fully reconciled, ordinary industrial supply invoice. No
         red flags. Exists so the auditor's false-accusation rate can
         be measured against something legitimate.
    """
 
    def __init__(self, db_connection_string):
        self.conn_str = db_connection_string
 
    def run_seed(self):
        """Executes the complete TrueLock seeding process within a single transaction."""
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                try:
                    # Fail fast configurations
                    cur.execute("SET LOCAL lock_timeout = '5s';")
                    cur.execute("SET LOCAL statement_timeout = '30s';")
 
                    self._seed_entities(cur)
                    self._seed_providers(cur)
                    self._seed_accounts(cur)
                    self._seed_invoices(cur)
                    self._seed_transactions_and_payments(cur)
                    self._run_integrity_guards(cur)
 
                    conn.commit()
                    print("Seeding completed successfully. Control case and 3 fraud cases loaded.")
                except Exception as e:
                    conn.rollback()
                    print(f"Seeding failed. Transaction rolled back. Error: {e}")
                    raise
 
    def _seed_entities(self, cur):
        # Combines fraud case 1 (Acme), control (Pemex/Normal Supplier),
        # fraud case 2 (EFOS shell, government receiver, diverted-payment
        # payee), and fraud case 3 (three fresh shells + collector).
        cur.execute("""
            INSERT INTO entities (id, rfc, name, entity_type) VALUES
                ('entity-acme', 'AAA010101AAA', 'Acme Manufacturing, S.A. de C.V.', 'company'),
                ('entity-provider', 'PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', 'company'),
                ('entity-normal-supplier', 'NORM850101AB1', 'Industrias Manufactureras Normales, S.A. de C.V.', 'company'),
                ('entity-pemex', 'PEMX800101001', 'Petroleos Mexicanos', 'company'),
                ('entity-investigator', NULL, 'Maria Lopez', 'individual'),
                ('entity-shell-efos', 'EFOS701010SAT', 'Comercializadora EFOS del Sur, S.A. de C.V.', 'company'),
                ('entity-gobierno', 'GES010101GOB', 'Gobierno Estatal Ejemplo', 'company'),
                ('entity-tercero', 'TER010101TER', 'Tercero Desconocido, S.A. de C.V.', 'company'),
                ('entity-shell-a', 'SHLA240115SH1', 'Servicios Fantasma Alpha, S.A. de C.V.', 'company'),
                ('entity-shell-b', 'SHLB240118SH2', 'Servicios Fantasma Beta, S.A. de C.V.', 'company'),
                ('entity-shell-c', 'SHLC240122SH3', 'Servicios Fantasma Gamma, S.A. de C.V.', 'company'),
                ('entity-collector', 'COLE180101CO1', 'Consultoria Acumuladora Estrategica, S.A. de C.V.', 'company')
            ON CONFLICT (id) DO UPDATE SET
                rfc = EXCLUDED.rfc, name = EXCLUDED.name, entity_type = EXCLUDED.entity_type;
        """)
 
    def _seed_providers(self, cur):
        # Idempotent provider load preserving EFOS status. Note
        # EFOS701010SAT is seeded already DEFINITIVO: unlike Proveedor
        # Ejemplo (still UNKNOWN, pending app verification), this one is
        # already public knowledge per the SAT 69-B gazette, so there is
        # nothing left to "discover" - the CASE guard still protects it
        # in case a later re-seed tries to downgrade it.
        cur.execute("""
            INSERT INTO providers (rfc, name, registration_date, address, phone, efos_status, efos_listed_date) VALUES
                ('PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', '2018-03-15', 'Av. Reforma 100', '+52-55-5555-0101', 'UNKNOWN', NULL),
                ('NORM850101AB1', 'Industrias Manufactureras Normales, S.A. de C.V.', '2008-04-12', 'Av. Industrial 450', '+52-81-5555-0185', 'UNKNOWN', NULL),
                ('EFOS701010SAT', 'Comercializadora EFOS del Sur, S.A. de C.V.', '2019-01-10', 'Camino Real 200, domicilio sin verificar, CDMX', '+52-55-0000-0000', 'DEFINITIVO', '2022-09-28'),
                ('COLE180101CO1', 'Consultoria Acumuladora Estrategica, S.A. de C.V.', '2018-01-01', 'Insurgentes Sur 1000, CDMX', '+52-55-1111-2222', 'UNKNOWN', NULL)
            ON CONFLICT (rfc) DO UPDATE SET
                name = EXCLUDED.name, registration_date = EXCLUDED.registration_date,
                efos_status = CASE WHEN providers.efos_status = 'UNKNOWN' THEN EXCLUDED.efos_status ELSE providers.efos_status END,
                efos_listed_date = CASE WHEN providers.efos_status = 'UNKNOWN' THEN EXCLUDED.efos_listed_date ELSE providers.efos_listed_date END;
        """)
 
    def _seed_accounts(self, cur):
        # Acme gets two accounts for round-trip detection; the fan-in
        # shells (SHLA/SHLB/SHLC) and the diversion payee (tercero) each
        # get one account, all feeding into a single collector/receiver
        # account per case.
        cur.execute("""
            INSERT INTO accounts (account_no, entity_id, bank) VALUES
                ('012345678901234567', 'entity-acme', 'Banco Demo'),
                ('987654321098765432', 'entity-provider', 'Banco Demo'),
                ('111122223333444455', 'entity-acme', 'Banco Demo'),
                ('444455556666777788', 'entity-normal-supplier', 'Banco Demo'),
                ('999988887777666655', 'entity-pemex', 'Banco Demo'),
                ('555566667777888899', 'entity-gobierno', 'Banco Demo'),
                ('222233334444555566', 'entity-tercero', 'Banco Demo'),
                ('666677778888999900', 'entity-shell-efos', 'Banco Demo'),
                ('111100002222333344', 'entity-shell-a', 'Banco Demo'),
                ('222200003333444455', 'entity-shell-b', 'Banco Demo'),
                ('333300004444555566', 'entity-shell-c', 'Banco Demo'),
                ('444400005555666677', 'entity-collector', 'Banco Demo')
            ON CONFLICT (account_no) DO NOTHING;
        """)
 
    def _seed_invoices(self, cur):
        # Generates CFDI 4.0 exact structure.
        #
        # FRAUD CASE 2 invoice: PPD (deferred), intangible/inflated
        # concept, issued by an already-blacklisted RFC.
        #
        # FRAUD CASE 3 invoices: three separate suppliers, but the
        # concept text is word-for-word identical across all three -
        # a template-reuse signal that only shows up once you compare
        # invoices across "unrelated" entities.
        cur.execute("""
            INSERT INTO invoices (uuid, version, provider_rfc, receiver_rfc, issue_date, amount, subtotal, taxes, currency, payment_method, payment_form, cfdi_type, concept) VALUES
                ('11111111-1111-4111-8111-111111111111', '4.0', 'PRO010101PRO', 'AAA010101AAA', '2025-01-15', 1160.00, 1000.00, 160.00, 'MXN', 'PUE', '03', 'I', 'Servicios de consultoria'),
                ('22222222-2222-4222-8222-222222222222', '4.0', 'NORM850101AB1', 'PEMX800101001', '2024-03-10', 1392000.00, 1200000.00, 192000.00, 'MXN', 'PUE', '03', 'I', 'Suministro de tuberia de acero estructural'),
                ('33333333-3333-4333-8333-333333333333', '4.0', 'EFOS701010SAT', 'GES010101GOB', '2024-01-15', 11600000.00, 10000000.00, 1600000.00, 'MXN', 'PPD', '99', 'I', 'Asesoria estrategica digital intangible inexplicable'),
                ('44444444-4444-4444-8444-444444444444', '4.0', 'COLE180101CO1', 'SHLA240115SH1', '2024-02-01', 580000.00, 500000.00, 80000.00, 'MXN', 'PUE', '03', 'I', 'Servicios de consultoria estrategica empresarial'),
                ('55555555-5555-4555-8555-555555555555', '4.0', 'COLE180101CO1', 'SHLB240118SH2', '2024-02-01', 580000.00, 500000.00, 80000.00, 'MXN', 'PUE', '03', 'I', 'Servicios de consultoria estrategica empresarial'),
                ('66666666-6666-4666-8666-666666666666', '4.0', 'COLE180101CO1', 'SHLC240122SH3', '2024-02-02', 580000.00, 500000.00, 80000.00, 'MXN', 'PUE', '03', 'I', 'Servicios de consultoria estrategica empresarial')
            ON CONFLICT (uuid) DO NOTHING;
        """)
 
    def _seed_transactions_and_payments(self, cur):
        # Forward insert transactions without payment ID.
        #
        # FRAUD CASE 2: the settlement goes to entity-tercero's account,
        # not to entity-shell-efos's own declared account - the invoiced
        # provider never actually receives the money.
        #
        # FRAUD CASE 3: three individually clean settlements (each
        # transaction matches its own invoice/payment exactly), but all
        # three land in the same collector account within a two-day
        # span - the fraud signal is topological, not arithmetic.
        cur.execute("""
            INSERT INTO transactions (id, from_account, to_account, transaction_date, amount, related_payment_id) VALUES
                ('transaction-demo-001', '012345678901234567', '987654321098765432', '2025-01-16', 1160.00, NULL),
                ('transaction-demo-002', '987654321098765432', '111122223333444455', '2025-01-17', 900.00, NULL),
                ('transaction-normal-001', '999988887777666655', '444455556666777788', '2024-03-12', 1392000.00, NULL),
                ('transaction-efos-001', '555566667777888899', '222233334444555566', '2024-01-16', 11600000.00, NULL),
                ('transaction-fanin-001', '111100002222333344', '444400005555666677', '2024-02-03', 580000.00, NULL),
                ('transaction-fanin-002', '222200003333444455', '444400005555666677', '2024-02-03', 580000.00, NULL),
                ('transaction-fanin-003', '333300004444555566', '444400005555666677', '2024-02-04', 580000.00, NULL)
            ON CONFLICT (id) DO NOTHING;
        """)
 
        # Insert payments referencing transactions
        cur.execute("""
            INSERT INTO payments (id, related_invoice_uuid, payment_date, amount, payment_form, currency, previous_balance, remaining_balance, transaction_ids) VALUES
                ('payment-demo-001', '11111111-1111-4111-8111-111111111111', '2025-01-16', 1160.00, '03', 'MXN', 1160.00, 0.00, ARRAY['transaction-demo-001']::TEXT[]),
                ('payment-normal-001', '22222222-2222-4222-8222-222222222222', '2024-03-12', 1392000.00, '03', 'MXN', 1392000.00, 0.00, ARRAY['transaction-normal-001']::TEXT[]),
                ('payment-efos-001', '33333333-3333-4333-8333-333333333333', '2024-01-16', 11600000.00, '03', 'MXN', 11600000.00, 0.00, ARRAY['transaction-efos-001']::TEXT[]),
                ('payment-fanin-001', '44444444-4444-4444-8444-444444444444', '2024-02-03', 580000.00, '03', 'MXN', 580000.00, 0.00, ARRAY['transaction-fanin-001']::TEXT[]),
                ('payment-fanin-002', '55555555-5555-4555-8555-555555555555', '2024-02-03', 580000.00, '03', 'MXN', 580000.00, 0.00, ARRAY['transaction-fanin-002']::TEXT[]),
                ('payment-fanin-003', '66666666-6666-4666-8666-666666666666', '2024-02-04', 580000.00, '03', 'MXN', 580000.00, 0.00, ARRAY['transaction-fanin-003']::TEXT[])
            ON CONFLICT (id) DO NOTHING;
        """)
 
        # Back-fill mutual relations
        cur.execute("""
            UPDATE transactions SET related_payment_id = 'payment-demo-001' WHERE id = 'transaction-demo-001';
            UPDATE transactions SET related_payment_id = 'payment-normal-001' WHERE id = 'transaction-normal-001';
            UPDATE transactions SET related_payment_id = 'payment-efos-001' WHERE id = 'transaction-efos-001';
            UPDATE transactions SET related_payment_id = 'payment-fanin-001' WHERE id = 'transaction-fanin-001';
            UPDATE transactions SET related_payment_id = 'payment-fanin-002' WHERE id = 'transaction-fanin-002';
            UPDATE transactions SET related_payment_id = 'payment-fanin-003' WHERE id = 'transaction-fanin-003';
        """)
 
    def _run_integrity_guards(self, cur):
        # Evaluates constraints before final commit. Each fraud case
        # must still be internally consistent (right amounts, right row
        # counts) - the fraud lives in the topology/context, not in
        # broken arithmetic that a guard should have caught.
        cur.execute("""
            DO $$
            DECLARE
                dangling TEXT;
                bad_total NUMERIC;
            BEGIN
                SELECT string_agg(i.uuid::TEXT, ', ') INTO dangling FROM invoices i
                WHERE i.amount <> i.subtotal + i.taxes;
                IF dangling IS NOT NULL THEN RAISE EXCEPTION 'invoice amount <> subtotal + taxes for: %', dangling; END IF;
 
                SELECT count(*) INTO bad_total FROM transactions WHERE id IN ('transaction-demo-001', 'transaction-demo-002');
                IF bad_total <> 2 THEN RAISE EXCEPTION 'expected 2 demo transactions, found %', bad_total; END IF;
 
                SELECT count(*) INTO bad_total FROM transactions WHERE id = 'transaction-efos-001';
                IF bad_total <> 1 THEN RAISE EXCEPTION 'expected 1 EFOS diversion transaction, found %', bad_total; END IF;
 
                SELECT count(*) INTO bad_total FROM transactions
                 WHERE id IN ('transaction-fanin-001', 'transaction-fanin-002', 'transaction-fanin-003');
                IF bad_total <> 3 THEN RAISE EXCEPTION 'expected 3 fan-in transactions, found %', bad_total; END IF;
            END
            $$;
        """)
 
if __name__ == "__main__":
    seeder = TrueLockSeeder("dbname=truelock user=postgres password=secret")
    seeder.run_seed()
