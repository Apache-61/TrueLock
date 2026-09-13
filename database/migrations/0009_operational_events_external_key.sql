-- Fase 7: durable operational events keyed by external case id (demo-safe).
ALTER TABLE truelock.operational_events
    ADD COLUMN IF NOT EXISTS external_case_key text;

CREATE INDEX IF NOT EXISTS operational_events_external_case_time_idx
    ON truelock.operational_events (external_case_key, occurred_at DESC);

COMMENT ON COLUMN truelock.operational_events.external_case_key IS
    'Demo/API case id (e.g. CASE-LEAD-...) when no UUID case row is available.';

INSERT INTO truelock.schema_migrations(version)
VALUES ('0009_operational_events_external_key')
ON CONFLICT DO NOTHING;
