import psycopg2
from psycopg2 import sql

class TrueLockSeeder:
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
                    print("Seeding completed successfully. Baseline and anomalies loaded.")
                except Exception as e:
                    conn.rollback()
                    print(f"Seeding failed. Transaction rolled back. Error: {e}")
                    raise

    def _seed_entities(self, cur):
        # Combines anomaly (Acme) and control (Pemex/Normal Supplier) entities
        cur.execute("""
            INSERT INTO entities (id, rfc, name, entity_type) VALUES
                ('entity-acme', 'AAA010101AAA', 'Acme Manufacturing, S.A. de C.V.', 'company'),
                ('entity-provider', 'PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', 'company'),
                ('entity-normal-supplier', 'NORM850101AB1', 'Industrias Manufactureras Normales, S.A. de C.V.', 'company'),
                ('entity-pemex', 'PEMX800101001', 'Petroleos Mexicanos', 'company'),
                ('entity-investigator', NULL, 'Maria Lopez', 'individual')
            ON CONFLICT (id) DO UPDATE SET
                rfc = EXCLUDED.rfc, name = EXCLUDED.name, entity_type = EXCLUDED.entity_type;
        """)

    def _seed_providers(self, cur):
        # Idempotent provider load preserving EFOS status
        cur.execute("""
            INSERT INTO providers (rfc, name, registration_date, address, phone, efos_status, efos_listed_date) VALUES
                ('PRO010101PRO', 'Proveedor Ejemplo, S.A. de C.V.', '2018-03-15', 'Av. Reforma 100', '+52-55-5555-0101', 'UNKNOWN', NULL),
                ('NORM850101AB1', 'Industrias Manufactureras Normales, S.A. de C.V.', '2008-04-12', 'Av. Industrial 450', '+52-81-5555-0185', 'UNKNOWN', NULL)
            ON CONFLICT (rfc) DO UPDATE SET
                name = EXCLUDED.name, registration_date = EXCLUDED.registration_date,
                efos_status = CASE WHEN providers.efos_status = 'UNKNOWN' THEN EXCLUDED.efos_status ELSE providers.efos_status END,
                efos_listed_date = CASE WHEN providers.efos_status = 'UNKNOWN' THEN EXCLUDED.efos_listed_date ELSE providers.efos_listed_date END;
        """)

    def _seed_accounts(self, cur):
        # Acme gets two accounts for round-trip detection; others get one
        cur.execute("""
            INSERT INTO accounts (account_no, entity_id, bank) VALUES
                ('012345678901234567', 'entity-acme', 'Banco Demo'),
                ('987654321098765432', 'entity-provider', 'Banco Demo'),
                ('111122223333444455', 'entity-acme', 'Banco Demo'),
                ('444455556666777788', 'entity-normal-supplier', 'Banco Demo'),
                ('999988887777666655', 'entity-pemex', 'Banco Demo')
            ON CONFLICT (account_no) DO NOTHING;
        """)

    def _seed_invoices(self, cur):
        # Generates CFDI 4.0 exact structure
        cur.execute("""
            INSERT INTO invoices (uuid, version, provider_rfc, receiver_rfc, issue_date, amount, subtotal, taxes, currency, payment_method, payment_form, cfdi_type, concept) VALUES
                ('11111111-1111-4111-8111-111111111111', '4.0', 'PRO010101PRO', 'AAA010101AAA', '2025-01-15', 1160.00, 1000.00, 160.00, 'MXN', 'PUE', '03', 'I', 'Servicios de consultoria'),
                ('22222222-2222-4222-8222-222222222222', '4.0', 'NORM850101AB1', 'PEMX800101001', '2024-03-10', 1392000.00, 1200000.00, 192000.00, 'MXN', 'PUE', '03', 'I', 'Suministro de tuberia de acero estructural')
            ON CONFLICT (uuid) DO NOTHING;
        """)

    def _seed_transactions_and_payments(self, cur):
        # Forward insert transactions without payment ID
        cur.execute("""
            INSERT INTO transactions (id, from_account, to_account, transaction_date, amount, related_payment_id) VALUES
                ('transaction-demo-001', '012345678901234567', '987654321098765432', '2025-01-16', 1160.00, NULL),
                ('transaction-demo-002', '987654321098765432', '111122223333444455', '2025-01-17', 900.00, NULL),
                ('transaction-normal-001', '999988887777666655', '444455556666777788', '2024-03-12', 1392000.00, NULL)
            ON CONFLICT (id) DO NOTHING;
        """)
        
        # Insert payments referencing transactions
        cur.execute("""
            INSERT INTO payments (id, related_invoice_uuid, payment_date, amount, payment_form, currency, previous_balance, remaining_balance, transaction_ids) VALUES
                ('payment-demo-001', '11111111-1111-4111-8111-111111111111', '2025-01-16', 1160.00, '03', 'MXN', 1160.00, 0.00, ARRAY['transaction-demo-001']::TEXT[]),
                ('payment-normal-001', '22222222-2222-4222-8222-222222222222', '2024-03-12', 1392000.00, '03', 'MXN', 1392000.00, 0.00, ARRAY['transaction-normal-001']::TEXT[])
            ON CONFLICT (id) DO NOTHING;
        """)

        # Back-fill mutual relations
        cur.execute("""
            UPDATE transactions SET related_payment_id = 'payment-demo-001' WHERE id = 'transaction-demo-001';
            UPDATE transactions SET related_payment_id = 'payment-normal-001' WHERE id = 'transaction-normal-001';
        """)

    def _run_integrity_guards(self, cur):
        # Evaluates constraints before final commit
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
            END
            $$;
        """)

if __name__ == "__main__":
    seeder = TrueLockSeeder("dbname=truelock user=postgres password=secret")
    seeder.run_seed()
    # Example execution
    # seeder = TrueLockSeeder("dbname=truelock user=postgres password=secret")
    # seeder.run_seed()
