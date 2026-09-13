#!/usr/bin/env bash
set -euo pipefail
cd /app
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "Applying migrations..."
  bash scripts/migrate.sh || echo "migrate warning"
  bash scripts/seed_demo.sh || echo "seed warning"
fi
exec uvicorn truelock.api.app:app --host 0.0.0.0 --port "${PORT:-8000}"
