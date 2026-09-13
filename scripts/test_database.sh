#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=scripts/_psql_env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_psql_env.sh"

"${PSQL[@]}" -v ON_ERROR_STOP=1 --single-transaction \
  -f database/tests/001_demo_invariants.sql
