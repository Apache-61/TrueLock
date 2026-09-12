# domain/entities/

**Purpose:** language-level (Python/TypeScript) implementations of the
JSON Schema contracts in `domain/schemas/` — e.g. Pydantic models for the
backend, generated/hand-written TS types for the frontend.

**What goes here:** typed classes/interfaces that mirror a schema 1:1, plus
their (de)serialization. No business logic beyond validation.

**What does not go here:** detection rules (`detection/rules/`), the JSON
Schema itself (`domain/schemas/`, which is the source of truth — these
entities must not drift from it), agent behavior (`agent/`).

**Depends on:** `domain/schemas/*.schema.json`.

Empty at bootstrap time — implemented as part of `TASK-001`
(canonical domain data ingestion & normalization).
