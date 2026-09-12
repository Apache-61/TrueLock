# Security policy — TrueLock

## Threat model for this build

This is a hackathon forensic-audit demo handling (initially synthetic, and
potentially later semi-real) financial and tax data. Treat the following as
untrusted by default:

- **Model output.** Gemini (or any LLM) output is never trusted as fact. It
  cannot compute amounts, decide EFOS status, or assert evidence identity —
  those are deterministic (`ARCHITECTURE.md` §2). Structured agent output is
  validated against the schemas in `docs/contracts/` before use; malformed
  output is retried with a strict schema, not silently accepted.
- **Uploaded/ingested data.** CFDI XML, CSV exports, and any judge-provided
  "hidden fraud" dataset are parsed defensively (`scripts/ingest/`) —
  reject rather than best-effort-guess on malformed records.
- **External API responses** (SAT lookups, Gemini, Solana RPC) — validate
  shape and status before use; never `eval`/`exec` a response.

## Secrets

- No secret, API key, or token is ever committed. `.env.example` lists the
  variable **names** only.
- `.gitignore` excludes `.env`, `*.key`, `.state/` runtime files that could
  contain tokens, and any local credential cache.
- If a secret is committed by accident: rotate it immediately, then remove
  it from history — do not just delete the file in a new commit.
- Each of the four workstations uses its own scoped API key/project (see
  `orchestrator/policies/provider-pool.yaml`); do not share personal
  credentials between machines or commit them to shared config.

## The forensic agent's authority

- The forensic agent (`agent/`) has **read-only** access to financial data
  and the tool surface in `docs/contracts/agent-tools.md`. It never
  receives unrestricted SQL and never has write access to this
  repository's source code.
- Development AI workers (the ones building this repo, per
  `orchestrator/`) never have authority over a forensic conclusion, and
  are governed by a separate policy/prompt from the forensic agent
  (`ARCHITECTURE.md` §6, `CONTRIBUTING.md` §7).

## Regulatory data handling

- SAT 69-B/EFOS status is stored and displayed as **fiscal status**, never
  auto-translated to "this is fraud" (`docs/regulatory/sat-69b.md`). This
  is a security/integrity concern as much as a product one: mislabeling a
  taxpayer's status is a real-world harm, not just a demo bug.
- Any real (non-synthetic) taxpayer or bank data introduced for testing
  must be anonymized or must stay in `data/raw/` (gitignored) and never be
  committed.

## Reporting a concern

During the hackathon: open an issue with label `type:security` and ping the
team directly — do not wait for the normal task queue for anything that
could leak a credential or expose real financial data. After the
hackathon: contact the repository owner directly rather than filing a
public issue for anything not yet fixed.
