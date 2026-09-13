# TrueLock — The Forensic Auditor

[![CI](https://github.com/apache-61/truelock/actions/workflows/ci.yml/badge.svg)](https://github.com/apache-61/truelock/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/next.js-14-black.svg)](https://nextjs.org/)

TrueLock is an autonomous forensic accounting intelligence platform built for complex corporate fraud, rapid pass-through fund routing, and circular invoice/return schemes.

Instead of operating as an ungrounded LLM classifier or a brittle rule table, TrueLock strictly separates **deterministic computational authority** (reconciliation, graph traversal, detector execution, exposure accounting) from **bounded generative investigation** (Google Gemini function calling over an allowlisted tool set).

---

## Architecture Overview

```text
                                  +-----------------------------+
                                  |     Next.js 14 Frontend     |
                                  |  (Dashboard, Trail, Q&A)    |
                                  +--------------+--------------+
                                                 | REST / JSON
                                                 v
+-----------------------------------------------------------------------------------------+
|                                    TrueLock Backend                                     |
|                                                                                         |
|   +-----------------------+     +-----------------------+     +---------------------+   |
|   |   Detection Engine    | --> | Bounded Investigator  | <-> |    Google Gemini    |   |
|   | (Cycle, Pass-through) |     |   (Evidence Chain)    |     | (Function Calling)  |   |
|   +-----------+-----------+     +-----------+-----------+     +---------------------+   |
|               |                             |                                           |
|               v                             v                                           |
|   +-----------------------------------------------------+                               |
|   |                 Typed Repositories                  |                               |
|   |        (Entities, Accounts, Transactions, CFDIs)    |                               |
|   +--------------------------+--------------------------+                               |
+------------------------------|----------------------------------------------------------+
                               v
               +-------------------------------+
               |    PostgreSQL / Migrations    |
               | (Static Fixtures & Demo Seed) |
               +-------------------------------+
```

### Core Invariants

1. **Deterministic Authority Boundary**: Code (Python) owns parsing, reconciliation, graph traversal, and exposure arithmetic. Gemini selects read-only tools and interprets findings.
2. **Proof Before Accusation**: All leads must terminate as `SUPPORTED`, `REJECTED`, or `INSUFFICIENT_EVIDENCE`. High risk is never asserted without direct economic linkage.
3. **No Edge Double-Counting**: Total financial exposure is calculated solely from unique root originating transactions ($1,000,000 MXN), never by summing intermediate hops in cyclical graphs.
4. **Contextual Regulatory Evidence**: SAT Art. 69-B (EFOS) listing is contextual evidence only, not standalone proof of fraud.
5. **Real, Safe Server-Side Agent**: Uses official Google Gemini API with server-side keys. No raw SQL, no system shell, bounded steps, and automated offline fallback.

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- **`psql`** (PostgreSQL client CLI) — required for migrations, seeds, and database tests
- PostgreSQL 16+ server (local install or `docker compose up -d postgres`)

Verify tools before working on the database layer:

```bash
bash scripts/check_requirements.sh
```

Install `psql` if missing:

| Platform | Command |
| --- | --- |
| Ubuntu / Debian | `sudo apt-get install postgresql-client` |
| macOS | `brew install libpq && brew link --force libpq` |
| Windows | `winget install PostgreSQL.PostgreSQL.16` (restart shell) |

### 2. Backend Setup
```bash
# Clone and enter repo
git clone https://github.com/apache-61/truelock.git
cd TrueLock

# Create environment file
cp .env.example .env

# Install backend dependencies
pip install -e ".[dev]"

# (Optional) Add your Google Gemini API Key in .env:
# GEMINI_API_KEY=your_key_here
```

### 3. Start PostgreSQL Database
```bash
# Requires Docker Desktop (Windows/macOS) or Docker Engine (Linux)
docker compose up -d postgres

export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
export TRUELOCK_TEST_DATABASE_URL="$DATABASE_URL"

# Preferred on Windows: migrate+seed inside Compose (reliable psql)
docker compose --profile app run --rm migrate

# Or native scripts when psql handles the URL / PG* env vars:
# bash scripts/migrate.sh && bash scripts/seed_demo.sh
bash scripts/test_database.sh
```

Host port **5433** avoids clashing with a local Windows PostgreSQL install on 5432.

### 4. Run the Backend API
```bash
uvicorn truelock.api.app:app --reload --port 8000
```
API documentation available at `http://localhost:8000/docs`.

### 5. Start the Frontend Application
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to launch the Forensic Auditor dashboard.

---

## Automated Demo & Verification Commands

Run the demo suite directly from the command line:

```bash
# 1. Print seed scenario summary
python scripts/seed_demo.py

# 2. Verify all forensic invariants and calculations
python scripts/verify_demo.py

# 3. Execute the full end-to-end investigation walkthrough
python scripts/run_demo.py

# 4. Run the entire backend test suite (integration DB tests need psql + DATABASE_URL)
export TRUELOCK_TEST_DATABASE_URL="$DATABASE_URL"
pytest -v
```

---

## Repository Structure

```text
TrueLock/
├── backend/
│   ├── Dockerfile
│   └── src/truelock/
│       ├── agent/             # Gemini client, tool registry, investigator loop
│       ├── api/               # FastAPI routes & endpoints
│       ├── database/          # Repository interfaces & in-memory/SQL implementations
│       ├── detection/         # Deterministic fraud detectors (cycle, pass-through, dup)
│       ├── domain/            # Canonical Pydantic models & JSON schemas
│       ├── evidence/          # Evidence provenance, hashing & exposure accounting
│       ├── seeder/            # Demo scenarios & CFDI/bank ingestion
│       ├── services/          # Investigation & judge Q&A services
│       └── settings.py        # Typed server settings
├── frontend/                  # Next.js 14 forensic audit UI
├── database/
│   ├── migrations/            # Ordered, immutable PostgreSQL migrations
│   └── seeds/                 # Versioned SQL demo seeds
├── config/                    # Agent providers, usage ledger, demo config
├── docs/                      # Architecture, forensic principles, demo script, decisions
├── scripts/                   # run_demo.py, seed_demo.py, verify_demo.py
├── tests/                     # Unit, contract, and integration tests
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Documentation

- **Judge / reviewer start here:** hosted [https://truelockfa.tech/docs](https://truelockfa.tech/docs) (local `http://localhost:3000/docs`) or markdown [`docs/challenge/README.md`](docs/challenge/README.md) → runbook → API → training. Pack: `dist/docs-pack/` (`dist/truelock-docs-pack.zip`). Cloud DNS steps: [`docs/ops/hosted-tech-domain.md`](docs/ops/hosted-tech-domain.md).
- [`docs/architecture.md`](docs/architecture.md) — Detailed technical stack, boundaries, and system components.
- [`docs/forensic-principles.md`](docs/forensic-principles.md) — Grounding rules, evidence admissibility, and exposure standards.
- [`docs/demo/README.md`](docs/demo/README.md) · [`docs/demo-script.md`](docs/demo-script.md) — Demo path and spoken walkthrough.
- [`docs/deployment.md`](docs/deployment.md) — Compose; Postgres host port **5433**.
- [`docs/testing.md`](docs/testing.md) — Verification baseline.
- [`docs/decisions.md`](docs/decisions.md) — Active architectural decisions.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Code style, pull request guidelines, and development standards.
