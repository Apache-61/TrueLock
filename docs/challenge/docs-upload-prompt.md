# Paste into a second Cursor chat (docs packaging only)

You are working in the TrueLock repo at c:\Developer\Hackathon\TrueLock.

MISSION (docs packaging / upload only — do NOT change agent training):
Prepare and upload/publish the project documentation for the hackathon while another chat trains the agent.

STRICT FILE BOUNDARIES — you MAY edit/create:
- README.md (entry links only; do not rewrite product architecture unless broken)
- docs/demo/runbook.md, docs/demo/README.md, docs/demo-script.md
- docs/challenge/README.md, docs/challenge/traceability-matrix.md
- docs/deployment.md, docs/testing.md (paths/ports only if stale)
- A single hackathon package folder if needed, e.g. dist/docs-pack/ with copies or a clear INDEX.md
- .env.example comments that help judges (no real secrets)

STRICT — you MUST NOT edit:
- backend/src/truelock/agent/policy/**
- backend/src/truelock/agent/eval/**
- data/eval_corpus/**
- detector/scoring/investigation core logic unless a doc link is wrong (fix the link, not the code)

DELIVERABLES:
1. A short “Judge / reviewer” index: start here → runbook → contracts → training overview (link to docs/agent/training.md, do not rewrite training content).
2. Verify host Postgres port is documented as 5433 where relevant (docker-compose maps 5433:5432).
3. Produce an upload-ready artifact: either (a) instructions to push/publish the docs tree, or (b) a zipped docs pack under dist/ with INDEX.md listing every included file. Prefer git push / GitHub release notes if remote exists; otherwise create dist/truelock-docs-pack.zip via a documented command.
4. Never commit secrets (.env, API keys). Do not commit unless I explicitly ask.

DONE when: INDEX or README points judges to a 5-minute demo path, docs are consistent with current API (including /api/imports/* and inject-fraud), and you report the upload/pack location (URL or dist path).
