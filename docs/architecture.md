# TrueLock Architecture

## 1. System Overview

TrueLock investigates complex financial fraud schemes—specifically **round-trip invoicing**, **rapid pass-through fund transfers**, and **duplicate payments**—within Mexican corporate accounting environments (CFDI 4.0 XML, SPEI bank transfers, and SAT 69-B listings).

The system enforces a strict boundary between:
1. **Deterministic Processing (Code)**: Verification, arithmetic, cycle detection, exposure calculation, and finding admissibility.
2. **Generative Intelligence (Google Gemini)**: Hypothesis formulation, tool selection from an allowlist, evidence synthesis, and interactive Q&A.

---

## 2. Component Boundaries

### Backend (`backend/src/truelock/`)
- **`domain`**: Source-of-truth Pydantic models (`truelock.domain.models`) mirroring JSON Schema specifications in `schemas/`.
- **`detection`**: Deterministic detectors scanning transactions and invoices for cycles, rapid pass-throughs, and duplicate payments. Outputs prioritized `Lead` records.
- **`database`**: Repository layer with clean `Protocol` abstractions (`interfaces.py`), in-memory fixtures (`memory.py`), and PostgreSQL storage.
- **`agent`**: Official Google Gemini API integration (`gemini_client.py`), strictly bounded read-only tools (`tools.py`), and the investigator coordinator (`investigator.py`).
- **`evidence`**: Evidence collection with provenance hashes, finding admissibility rules, and root-flow exposure calculations (`exposure.py`).
- **`seeder`**: Deterministic demo scenario fixture loader and CFDI 4.0 / bank CSV normalizers (`seeder/ingestion/`).
- **`services`**: High-level orchestration for investigation lifecycles (`investigation_service.py`) and judge Q&A (`case_service.py`).
- **`api`**: FastAPI application exposing REST endpoints for leads, investigations, cases, and auditor Q&A.

### Frontend (`frontend/`)
- Next.js 14 application with TypeScript.
- Renders ranked leads, interactive money trail graph, "What the Auditor Did" timeline, evidence chains with hashes, and a judge Q&A terminal.
- Never imports backend code or executes detection rules directly; consumes typed REST contracts from the FastAPI backend.

### Database (`database/`)
- `database/migrations/`: Ordered, immutable schema migrations (`0001_init.sql`, `0002_payment_transaction_ids.sql`).
- `database/seeds/`: Static versioned demo data (`001_demo.sql`).

---

## 3. Investigation Lifecycle

```text
1. INGEST & RECONCILE
   Bank CSV / CFDI XML -> Canonical Models (Transaction, Invoice, Payment, Account)

2. DETECT
   Deterministic Detectors -> Signals -> Prioritized Leads (Risk Scored 0.0 - 1.0)

3. INVESTIGATE (Bounded Agent Loop)
   Lead -> Hypothesis -> Gemini Tool Selection -> Allowlisted Python Tool Execution
        -> Admissible Evidence Accumulation (Provenance & Hash) -> Stopping Criteria

4. EVALUATE & CLOSE
   Evidence Collector -> Finding (SUPPORTED / REJECTED / INSUFFICIENT_EVIDENCE)
                      -> Exposure Calculation (Root amount, returned offset)
                      -> Audited Case File
```
