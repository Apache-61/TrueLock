# evidence/

**Purpose:** assembles `Evidence` records produced during investigation
into the final `Case` (`docs/contracts/evidence.md`,
`docs/contracts/case.md`). This is the "auditor Q&A" and case-file layer
from `ARCHITECTURE.md` §1.

**What goes here:** evidence-chain storage/retrieval, case assembly logic
(deciding `SUBSTANTIATED`/`UNSUBSTANTIATED`/`INSUFFICIENT_EVIDENCE` per
documented rules, not model whim), case-file rendering (JSON → Markdown/
HTML), and — if time allows — the optional Solana notarization
(`history/decisions/ADR-0004-sponsor-tech-scope.md`) as a flagged
sub-module (`evidence/notarization/`).

**What does not go here:** the investigation loop itself (→
`agent/runtime/`), API serving (→ `backend/api/`, which reads from here).

**Depends on:** `domain/schemas/evidence.schema.json`,
`domain/schemas/case.schema.json`, `docs/contracts/case.md`.

**Owner:** Agent D (Agent/Evidence). Must not touch: `database/**`,
`frontend/**` (`CONTRIBUTING.md` §4).
