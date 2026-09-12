# scripts/setup/

**Purpose:** one-time repository setup that this session could not apply
directly (no repo-admin API access — see `PROJECT_STATE.md` → "Blocked").
A human with `gh` CLI and repo-admin rights runs these once.

- `create_labels.sh` — creates every label in `.github/ISSUE_TEMPLATE/`'s
  implied label set (see `tasks/README.md` priorities/status/areas).
- `branch_protection.sh` — configures `main` branch protection (required
  PR, required status checks, required review) per `CONTRIBUTING.md` §3
  and `ARCHITECTURE.md` §11.

Run once, near the start of the hackathon (see the operating pack's
"first 20 minutes" checklist, `PROJECT_STATE.md`).
