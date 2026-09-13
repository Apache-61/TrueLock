#!/usr/bin/env bash
# Shared libpq setup for Windows-friendly and Render DATABASE_URL shapes.
# Source from other scripts after DATABASE_URL is set (or PG* vars alone).

# Git Bash (MSYS) may mangle URI-shaped env vars unless path conversion is off.
export MSYS_NO_PATHCONV="${MSYS_NO_PATHCONV:-1}"
export MSYS2_ARG_CONV_EXCL="${MSYS2_ARG_CONV_EXCL:-*}"

_is_msys() {
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

_export_sslmode_from_query() {
  local query="${1#\?}"
  [[ -z "$query" ]] && return 0
  local part
  IFS='&' read -r -a parts <<< "$query"
  for part in "${parts[@]}"; do
    case "$part" in
      sslmode=*)
        export PGSSLMODE="${part#sslmode=}"
        ;;
    esac
  done
}

if [[ -n "${PGHOST:-}" && -n "${PGUSER:-}" && -n "${PGDATABASE:-}" ]]; then
  PSQL=(psql -X)
elif [[ -n "${DATABASE_URL:-}" ]]; then
  # Linux/Render: pass the URI straight to libpq (handles missing port,
  # ?sslmode=require, and percent-encoded passwords). Avoids brittle parsing.
  if ! _is_msys; then
    PSQL=(psql "$DATABASE_URL" -X)
  # Optional port; optional ?query (sslmode etc). Host may be hostname or IP.
  elif [[ "${DATABASE_URL}" =~ ^postgres(ql)?://([^:/@]+):([^@]+)@([^:/?]+)(:([0-9]+))?/([^?]+)(\?.*)?$ ]]; then
    export PGUSER="${BASH_REMATCH[2]}"
    export PGPASSWORD="${BASH_REMATCH[3]}"
    export PGHOST="${BASH_REMATCH[4]}"
    export PGPORT="${BASH_REMATCH[6]:-5432}"
    export PGDATABASE="${BASH_REMATCH[7]}"
    _export_sslmode_from_query "${BASH_REMATCH[8]:-}"
    PSQL=(psql -X)
  else
    PSQL=(psql "$DATABASE_URL" -X)
  fi
else
  echo "DATABASE_URL or PGHOST/PGUSER/PGDATABASE is required" >&2
  exit 1
fi
