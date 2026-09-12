#!/usr/bin/env bash
# One-time branch protection setup for `main`. Requires the `gh` CLI,
# authenticated with repo-admin rights. This session's GitHub MCP tool
# surface has no branch-protection endpoint, so this has to be run by a
# human on a workstation with `gh` - see PROJECT_STATE.md -> "Blocked".
#
# Usage: GH_REPO=apache-61/truelock ./scripts/setup/branch_protection.sh
set -euo pipefail
REPO="${GH_REPO:?Set GH_REPO=owner/repo}"
BRANCH="${GH_BRANCH:-main}"

# Adjust `contexts` to match the actual job names in
# .github/workflows/ci.yml if they change.
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "repos/${REPO}/branches/${BRANCH}/protection" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=Contract validation + pytest" \
  -f "enforce_admins=false" \
  -f "required_pull_request_reviews[required_approving_review_count]=1" \
  -f "required_pull_request_reviews[require_code_owner_reviews]=true" \
  -f "restrictions="

echo "Branch protection applied to ${REPO}@${BRANCH}."
echo "Verify in the GitHub UI under Settings -> Branches - 'restrictions=null' via the API sometimes needs to be set through the UI instead if this call is rejected."
