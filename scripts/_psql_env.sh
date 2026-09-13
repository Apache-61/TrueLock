#!/usr/bin/env bash
# Shared libpq setup for Windows-friendly psql invocations.
# Source from other scripts after DATABASE_URL is set (or PG* vars alone).

# Git Bash (MSYS) may mangle URI-shaped env vars unless path conversion is off.
export MSYS_NO_PATHCONV="${MSYS_NO_PATHCONV:-1}"
export MSYS2_ARG_CONV_EXCL="${MSYS2_ARG_CONV_EXCL:-*}"

if [[ -n "${PGHOST:-}" && -n "${PGUSER:-}" && -n "${PGDATABASE:-}" ]]; then
  PSQL=(psql -X)
elif [[ -n "${DATABASE_URL:-}" ]]; then
  if [[ "${DATABASE_URL}" =~ ^postgres(ql)?://([^:/@]+):([^@]+)@([^:/]+):([0-9]+)/(.+)$ ]]; then
    export PGUSER="${BASH_REMATCH[2]}"
    export PGPASSWORD="${BASH_REMATCH[3]}"
    export PGHOST="${BASH_REMATCH[4]}"
    export PGPORT="${BASH_REMATCH[5]}"
    export PGDATABASE="${BASH_REMATCH[6]%%\?*}"
    PSQL=(psql -X)
  else
    PSQL=(psql "$DATABASE_URL" -X)
  fi
else
  echo "DATABASE_URL or PGHOST/PGUSER/PGDATABASE is required" >&2
  exit 1
fi
