#!/usr/bin/env bash
# Verify CLI tools required across the TrueLock repository.
set -euo pipefail

missing=()

if ! command -v psql >/dev/null 2>&1; then
  missing+=("psql — PostgreSQL client (required for migrations, seeds, and SQL invariant tests)")
fi

if ! command -v python >/dev/null 2>&1; then
  missing+=("python — Python 3.10+")
fi

if ! command -v node >/dev/null 2>&1; then
  missing+=("node — Node.js 18+ (frontend)")
fi

if ((${#missing[@]})); then
  echo "Missing required tools:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  echo "" >&2
  echo "Install psql:" >&2
  echo "  Ubuntu/Debian:  sudo apt-get install postgresql-client" >&2
  echo "  macOS:          brew install libpq && brew link --force libpq" >&2
  echo "  Windows:        winget install PostgreSQL.PostgreSQL.16" >&2
  echo "                  (restart the shell so psql is on PATH)" >&2
  echo "" >&2
  echo "PostgreSQL server for local development:" >&2
  echo "  docker compose up -d postgres" >&2
  exit 1
fi

echo "psql:   $(psql --version)"
echo "python: $(python --version 2>&1)"
echo "node:   $(node --version)"
echo "All required CLI tools are available."
