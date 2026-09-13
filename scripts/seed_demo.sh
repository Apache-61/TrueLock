#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=scripts/_psql_env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_psql_env.sh"

exists="$("${PSQL[@]}" -Atq -v ON_ERROR_STOP=1 \
  -c "SELECT EXISTS (SELECT 1 FROM truelock.cases WHERE display_id = 'CASE-DEMO-001')")"
if [[ "$exists" == "t" ]]; then
  echo "CASE-DEMO-001 already exists; seed not reapplied"
  exit 0
fi

"${PSQL[@]}" -v ON_ERROR_STOP=1 -f database/seeds/001_demo.sql
echo "CASE-DEMO-001 seeded from canonical demo_scenario alignment"
