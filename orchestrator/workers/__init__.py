"""AI development worker.

Implements the "AI task execution protocol" from `orchestrator/README.md`
end to end:

    TASK -> CLAIM -> BRANCH -> CLAUDE -> TEST -> HISTORY -> PR

Entry point: `orchestrator.workers.cli:main`, exposed on a workstation as
`worker start` (see `docs/orchestration/worker-setup.md`).

Module map
----------
config        environment/identity resolution (WORKER_ID, tokens, limits)
github        stdlib GitHub REST client + the read/write split used by --dry-run
tasks         parse a GitHub issue into a TaskSpec (priority, deps, paths)
claim         CLAIM -> VERIFY protocol (tasks/README.md, ADR-0003)
dependencies  eligibility gate (READY / authorized / deps merged / not blocked)
scope         allowed_paths / forbidden_paths enforcement over a diff
gitops        branch creation, commit, push -- never touches main
context       bounded context pack (never the whole repository history)
adapters      AI execution backends (claude_code, mock)
validation    formatter -> lint -> typecheck -> unit -> integration gates
handoff       task-result.json + history/ai-activity entry
pullrequest   PR body assembly against .github/pull_request_template.md
merge_policy  what may never be auto-merged
safety        run limits and destructive-command refusal
runner        the loop that ties all of the above together
"""
