# tests/contract/

Validates every interface in `docs/contracts/` stays well-formed. At
bootstrap time (no product code yet) this means: every JSON Schema file
under `domain/schemas/` is valid JSON with the required top-level keys,
and structural invariants (like `lead.schema.json`'s conditional
`discard_reason` requirement) parse correctly. As `backend/`, `agent/`,
and `frontend/` are implemented, add API-shape and tool-response-shape
tests here too (`docs/testing.md`).
