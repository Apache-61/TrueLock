#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

# Legacy 0001/0002 create unqualified tables. When the DB role name matches the
# canonical schema ("truelock"), PostgreSQL resolves "$user" to that schema and
# re-applying 0001 would try to create truelock.accounts referencing
# truelock.entities(id) — which does not exist. Force public for legacy files
# and skip them once the public tables are already present.
_legacy_public_ready() {
  psql "$DATABASE_URL" -X -Atq -v ON_ERROR_STOP=1 \
    -c "SELECT to_regclass('public.entities') IS NOT NULL AND to_regclass('public.accounts') IS NOT NULL"
}

for migration in database/migrations/*.sql; do
  version="$(basename "$migration" .sql)"

  if [[ "$version" == "0001_init" || "$version" == "0002_payment_transaction_ids" ]]; then
    if [[ "$(_legacy_public_ready)" == "t" ]]; then
      echo "skip $version"
      continue
    fi
    echo "apply $version"
    # SET LOCAL binds search_path for the single transaction that applies the file.
    psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 --single-transaction \
      -c "SET LOCAL search_path TO public" \
      -f "$migration"
    continue
  fi

  applied="$(psql "$DATABASE_URL" -X -Atq -v ON_ERROR_STOP=1 \
    -c "SELECT coalesce((SELECT EXISTS (SELECT 1 FROM truelock.schema_migrations WHERE version = '$version')), false)" 2>/dev/null || true)"
  if [[ "$applied" == "t" ]]; then
    echo "skip $version"
    continue
  fi
  echo "apply $version"
  psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 --single-transaction -f "$migration"
done
