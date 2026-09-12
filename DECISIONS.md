# Decisions — index

This file is an index. Each row links to the full record in
`history/decisions/`. A decision is anything in the "human authorization
required" list in `CONTRIBUTING.md` §5, or anything future contributors are
likely to ask "wait, why did we do it this way?" about.

Add a row here and a file in `history/decisions/ADR-XXXX-slug.md` (copy
`history/decisions/README.md`'s template) whenever such a decision is made.
Link the ADR from the task/PR that implements it.

| ID | Decision | Chosen | Status | Record |
|---|---|---|---|---|
| ADR-0001 | Overall stack (frontend/backend/DB/graph/LLM/orchestration) | Next.js+FastAPI+PostgreSQL+NetworkX+Gemini+custom agent loop | Accepted | [history/decisions/ADR-0001-stack.md](history/decisions/ADR-0001-stack.md) |
| ADR-0002 | Determinism/AI split for forensic reasoning | Rules+graph deterministic; Gemini investigates/narrates only | Accepted | [history/decisions/ADR-0002-determinism-ai-split.md](history/decisions/ADR-0002-determinism-ai-split.md) |
| ADR-0003 | Task coordination source of truth for 4 parallel workers | GitHub Issues + claim/verify-claim protocol | Accepted | [history/decisions/ADR-0003-task-coordination.md](history/decisions/ADR-0003-task-coordination.md) |
| ADR-0004 | Solana / ElevenLabs / Snowflake / MongoDB scope | Optional, outside critical path, bounded use only | Accepted | [history/decisions/ADR-0004-sponsor-tech-scope.md](history/decisions/ADR-0004-sponsor-tech-scope.md) |
| ADR-0005 | AI development worker: execution model and merge authority | Autonomous up to the PR, never past it; auto-merge triple-gated and off by default | Accepted | [history/decisions/ADR-0005-ai-development-worker.md](history/decisions/ADR-0005-ai-development-worker.md) |

Open (not yet decided) items are tracked in `PROJECT_STATE.md` → "Open
decisions", not here — this index is for decisions already made.
