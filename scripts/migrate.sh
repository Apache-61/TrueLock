#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

for migration in database/migrations/*.sql; do
  version="$(basename "$migration" .sql)"
  if [[ "$version" > "0002" ]]; then
    applied="$(psql "$DATABASE_URL" -X -Atq -v ON_ERROR_STOP=1 \
      -c "SELECT coalesce((SELECT EXISTS (SELECT 1 FROM truelock.schema_migrations WHERE version = '$version')), false)" 2>/dev/null || true)"
    if [[ "$applied" == "t" ]]; then
      echo "skip $version"
      continue
    fi
  fi
  echo "apply $version"
  psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 --single-transaction -f "$migration"
done
