# domain/

**Purpose:** the canonical, contract-frozen data model shared by every
other module. This is the single most collision-prone directory in the
repo — changing anything here ripples into `database/`, `detection/`,
`agent/`, `backend/`, and `frontend/`.

**What goes here:** JSON Schema files (`schemas/`) that are the source of
truth for a type; language-level entity definitions that implement those
schemas (`entities/`); shared enums (`enums/`).

**What does not go here:** business logic, detector rules, agent prompts,
API route definitions — those consume these contracts, they don't live
here.

**Depends on:** `research/sat/README.md` (regulatory grounding for the
Provider/EFOS fields), `docs/contracts/domain.md` (prose explanation of
every schema here).

**Owner:** primarily Agent B (Data/Backend) and Agent C (Detection/Graph)
per `CONTRIBUTING.md` §4. **Changing a file under `schemas/` requires
human authorization** (`CONTRIBUTING.md` §5) — every other module treats
these as frozen contracts.

## Contents

| File | What it defines |
|---|---|
| `schemas/entity.schema.json` | Any legal/natural person (company, provider, individual) |
| `schemas/provider.schema.json` | A supplier, including EFOS status |
| `schemas/account.schema.json` | A bank account |
| `schemas/invoice.schema.json` | A CFDI 4.0 invoice |
| `schemas/payment.schema.json` | Settlement of an invoice |
| `schemas/transaction.schema.json` | An account-to-account money movement |
| `schemas/detector_signal.schema.json` | A single detector's raw output |
| `schemas/lead.schema.json` | A candidate worth investigating |
| `schemas/evidence.schema.json` | A sourced claim gathered during investigation |
| `schemas/investigation_step.schema.json` | One agent tool call + typed decision |
| `schemas/case.schema.json` | The final auditable case file |
| `enums/efos-status.md` | The EFOS status enum and why it's modeled this way |

See `docs/contracts/domain.md` for the full canonical-model narrative
(why three layers: invoice → payment → transaction, not one collapsed
"financial transaction").
