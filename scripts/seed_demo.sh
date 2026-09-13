#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

exists="$(psql "$DATABASE_URL" -X -Atq -v ON_ERROR_STOP=1 \
  -c "SELECT EXISTS (SELECT 1 FROM truelock.cases WHERE display_id = 'CASE-DEMO-001')")"
if [[ "$exists" == "t" ]]; then
  echo "CASE-DEMO-001 already exists; seed not reapplied"
  exit 0
fi

psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f database/seeds/001_demo.sql
