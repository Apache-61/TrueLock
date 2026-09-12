#!/usr/bin/env bash
# One-time label setup. Requires the `gh` CLI, authenticated with
# repo-admin rights (`gh auth login`). This session's GitHub MCP tool
# surface has no label-admin endpoint, so this has to be run by a human
# on a workstation with `gh` - see PROJECT_STATE.md -> "Blocked".
#
# Usage: GH_REPO=apache-61/truelock ./scripts/setup/create_labels.sh
set -euo pipefail
REPO="${GH_REPO:?Set GH_REPO=owner/repo}"

create() {
  local name="$1" color="$2" desc="$3"
  gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" --force
}

# type:*
create "type:feature"     "1D76DB" "New capability"
create "type:bug"         "D73A4A" "Something is broken"
create "type:research"    "0E8A16" "Open question, not yet a decision"
create "type:experiment"  "FBCA04" "Time-boxed spike"
create "type:integration" "5319E7" "Connecting two modules or a sponsor service"
create "type:docs"        "0075CA" "Documentation"
create "type:security"    "B60205" "Security concern"
create "type:decision"    "BFD4F2" "Needs a recorded decision"

# priority:*
create "priority:P0" "B60205" "Blocks multiple modules / critical path"
create "priority:P1" "D93F0B" "Needed before demo"
create "priority:P2" "FBCA04" "Improves the demo"
create "priority:P3" "C5DEF5" "Nice to have, cut first"

# status:* (mirrors tasks/README.md state machine)
create "status:research"  "BFD4F2" "RESEARCH"
create "status:ready"     "0E8A16" "READY - unclaimed, safe to claim"
create "status:claimed"   "FBCA04" "CLAIMED - claim/verify protocol in progress"
create "status:active"    "1D76DB" "IN_PROGRESS / TESTING / READY_FOR_REVIEW"
create "status:blocked"   "D73A4A" "BLOCKED"
create "status:review"    "5319E7" "READY_FOR_REVIEW"
create "status:done"      "0E8A16" "MERGED / VERIFIED"

# area:*
for area in frontend backend data detection graph agent evidence database infra orchestrator; do
  create "area:$area" "C2E0C6" "Owned primarily by the $area module"
done

# execution:*
create "execution:auto"  "C5DEF5" "Can proceed without human sign-off"
create "execution:human" "B60205" "Requires human authorization (CONTRIBUTING.md §5)"

echo "Labels created/updated on $REPO."
