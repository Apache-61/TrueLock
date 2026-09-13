-- Expose tool I/O columns on the investigation timeline read model.
DROP VIEW IF EXISTS truelock.v_investigation_timeline;

CREATE VIEW truelock.v_investigation_timeline AS
SELECT
    s.case_id,
    s.investigation_id,
    s.thread_id,
    s.step_id,
    s.sequence,
    s.action,
    s.tool_name,
    s.reason_summary,
    s.tool_inputs,
    s.result_summary,
    s.provenance,
    s.errors,
    s.decision,
    s.started_at,
    s.completed_at,
    s.duration_ms,
    coalesce(array_agg(DISTINCT ie.evidence_id)
        FILTER (WHERE ie.evidence_id IS NOT NULL), ARRAY[]::uuid[]) AS input_evidence_ids,
    coalesce(array_agg(DISTINCT re.evidence_id)
        FILTER (WHERE re.evidence_id IS NOT NULL), ARRAY[]::uuid[]) AS result_evidence_ids
FROM truelock.investigation_steps s
LEFT JOIN truelock.investigation_step_input_evidence ie ON ie.step_id = s.step_id
LEFT JOIN truelock.investigation_step_result_evidence re ON re.step_id = s.step_id
GROUP BY s.case_id, s.investigation_id, s.thread_id, s.step_id, s.sequence,
         s.action, s.tool_name, s.reason_summary, s.tool_inputs, s.result_summary,
         s.provenance, s.errors, s.decision,
         s.started_at, s.completed_at, s.duration_ms;

INSERT INTO truelock.schema_migrations(version)
VALUES ('0010_investigation_timeline_tool_io')
ON CONFLICT DO NOTHING;
