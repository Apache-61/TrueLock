# Changelog

Records product-relevant changes — new capabilities, contract changes,
architecture shifts. Not every commit, not every typo fix; if it wouldn't
matter to someone re-reading this in a week, it doesn't go here.

## [Unreleased]

### Added
- Repository bootstrap: governance docs (`ARCHITECTURE.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `PROJECT_STATE.md`, `STATUS.md`,
  `DECISIONS.md`), full module directory scaffold, domain contracts
  (JSON Schema + docs), task queue with claim/verify-claim protocol,
  GitHub governance files (CODEOWNERS, PR/issue templates, CI baseline),
  and the orchestrator claim-protocol script.

No forensic-agent, detector, or frontend functionality exists yet — this
release is infrastructure only.
