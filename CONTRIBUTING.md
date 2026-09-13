# Contributing to TrueLock

Guidelines for contributing to the TrueLock Forensic Auditor platform.

---

## 1. Development Workflow

1. **Branching**: Branch from `main` using descriptive names:
   ```bash
   git checkout -b feature/short-description
   git checkout -b fix/short-description
   ```
2. **Local Environment**:
   ```bash
   # Install dependencies
   pip install -e ".[dev]"

   # Configure environment
   cp .env.example .env
   ```
3. **Run Checks Before Opening PR**:
   ```bash
   # Verify required CLI tools (psql, python, node)
   bash scripts/check_requirements.sh

   # Run all backend unit, integration, and contract tests
   export DATABASE_URL='postgresql://truelock:truelock_dev_only@localhost:5433/truelock'
   export TRUELOCK_TEST_DATABASE_URL="$DATABASE_URL"
   pytest -v

   # Run automated demo scenario verification
   python scripts/verify_demo.py

   # Build frontend
   cd frontend && npm install && npm run build
   ```
4. **Pull Requests**:
   - Open a PR against `main` using the provided PR template.
   - Include test output and screenshots where applicable.
   - Every PR requires human review before merge.

---

## 2. Naming & Placement Standards

- **Python packages, modules, functions, variables, SQL columns, YAML keys**: `snake_case`.
- **Python classes, Pydantic models, React components**: `PascalCase`.
- **React component filenames**: `PascalCase.tsx`.
- **React hooks**: `useThing.ts`.
- **API route groups**: Plural nouns (`/api/leads`, `/api/cases`, `/api/investigations`).
- **Database migrations**: Ordered and immutable (`0001_init.sql`, `0002_payment_transaction_ids.sql`).
- **Static seeds**: Numbered SQL scripts in `database/seeds/` (`001_demo.sql`).
- **Tests**: Named `test_<behavior>.py` located in `tests/unit/`, `tests/integration/`, or `tests/contract/`.
- **No catch-all directories**: Avoid `utils/`, `helpers/`, `misc/`. Create named modules with clear responsibilities.

---

## 3. Forensic & Evidence Invariants

When adding features, adhere strictly to the forensic principles in `docs/forensic-principles.md`:
1. **Deterministic Authority Boundary**: Code (Python), not the LLM, owns arithmetic, parsing, graph traversal, and exposure calculations.
2. **Proof Before Accusation**: All leads must resolve to `SUPPORTED`, `REJECTED`, or `INSUFFICIENT_EVIDENCE`. Never label an entity fraudulent without direct transactional proof.
3. **No Edge Double-Counting**: Output exposure is calculated from unique root transactions, never by summing downstream transfer graph hops.
4. **SAT 69-B is Contextual Evidence**: Tax authority listing is contextual evidence only; it never constitutes standalone proof of fraud.
5. **Bounded Agent Execution**: The Gemini agent executes allowlisted, read-only tools with capped steps and strict timeout limits. No raw SQL or shell access.
