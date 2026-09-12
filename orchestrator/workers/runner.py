"""The worker loop.

One pass over the queue, per `orchestrator/README.md` -> "AI task
execution protocol":

     1. identify the worker            9.  build a bounded context pack
     2. query GitHub                   10. run the AI adapter
     3. find READY tasks               11. enforce scope, run validation
     4. order by priority              12. write the handoff
     5. check dependencies             13. write history + timeline
     6. claim                          14. push and open a PR
     7. verify the claim               15. update the task's state
     8. create an isolated branch      16. look for the next task

Every step that can fail has exactly one honest outcome. The worker never
reports a task as done that it did not finish, never opens a
clean-looking PR over failing tests, and never edits a file outside the
task's declared paths.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import claim as claim_protocol
from . import merge_policy
from .adapters.base import AdapterError, AIResult, SuiteResult
from .config import WorkerConfig
from .context import build_context
from .dependencies import build_task_index, check_eligibility
from .gitops import Git, GitError
from .handoff import Handoff, append_timeline, new_run_id, requires_adr
from .pullrequest import build_human_authorization_proposal, build_pull_request
from .safety import RunLimits
from .scope import ScopeGuard
from .tasks import TaskQueue, TaskSpec, parse_issue
from .validation import Validator
from ..routing.ledger import UsageLedger
from ..routing.router import Provider, ProviderRouter

#: Label used when the repository's labels exist. Their absence is not an
#: error: `PROJECT_STATE.md` records that label creation still needs a
#: human with `gh` admin rights, so the worker must work without them.
READY_LABEL = "status:ready"


class Outcome:
    """Terminal states for one task attempt."""

    DONE = "DONE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    LOST_CLAIM = "LOST_CLAIM"
    PROPOSAL = "PROPOSAL"
    SKIPPED = "SKIPPED"


@dataclass
class TaskAttempt:
    """What happened to one task."""

    task_id: str
    issue_number: int
    outcome: str
    reason: str = ""
    branch: str = ""
    pr_url: str = ""
    run_id: str = ""


@dataclass
class RunSummary:
    """What happened to the whole run."""

    worker_id: str
    attempts: list[TaskAttempt] = field(default_factory=list)
    stop_reason: str = ""

    @property
    def exit_code(self) -> int:
        """0 unless something needs a human's attention."""
        if any(attempt.outcome == Outcome.FAILED for attempt in self.attempts):
            return 1
        return 0

    def render(self) -> str:
        if not self.attempts:
            return f"No task was attempted. {self.stop_reason}"
        lines = [f"Worker {self.worker_id} — {len(self.attempts)} task attempt(s):"]
        for attempt in self.attempts:
            line = f"  {attempt.task_id:10} {attempt.outcome:11} {attempt.reason}"
            if attempt.pr_url:
                line += f"\n{'':13}PR: {attempt.pr_url}"
            lines.append(line)
        if self.stop_reason:
            lines.append(f"Stopped: {self.stop_reason}")
        return "\n".join(lines)


class WorkerRunner:
    """Executes tasks until a limit, a blocker, or an empty queue stops it."""

    def __init__(
        self,
        config: WorkerConfig,
        client,
        adapter,
        *,
        limits: RunLimits | None = None,
        git: Git | None = None,
        validator: Validator | None = None,
        router: ProviderRouter | None = None,
        ledger: UsageLedger | None = None,
        allow_auto_merge: bool = False,
        log=print,
    ) -> None:
        self.config = config
        self.client = client
        self.adapter = adapter
        self.limits = (limits or RunLimits()).start()
        self.git = git or Git(config.repo_root, dry_run=config.dry_run)
        self.validator = validator or Validator(config.repo_root, dry_run=False)
        self.log = log
        self.router = router or ProviderRouter.from_policy(
            config.repo_root / "orchestrator" / "policies" / "provider-pool.yaml",
            logger=log,
        )
        self.ledger = ledger or UsageLedger(
            config.repo_root / ".state" / "usage.jsonl", dry_run=config.dry_run
        )
        self.allow_auto_merge = allow_auto_merge
        self.summary = RunSummary(worker_id=config.worker_id)
        self._register_provider()

    def _register_provider(self) -> None:
        """The Claude Code CLI is authenticated per workstation, so it is
        registered here rather than living in the Gemini key pool."""
        self.router.register(
            Provider(
                id="claude-code-cli",
                provider="anthropic",
                key_env="(workstation login)",
                max_session_budget_usd=0.0,
            )
        )

    # -- steps 2-5: find the next eligible task -----------------------
    def fetch_candidates(self) -> tuple[list[TaskSpec], dict[str, dict]]:
        """Read the queue from GitHub, the source of truth (ADR-0003)."""
        all_issues = self.client.list_issues(state="all")
        task_index = build_task_index(all_issues)

        labelled = [
            issue
            for issue in all_issues
            if (issue.get("state") or "open").lower() == "open"
            and READY_LABEL in {
                (label["name"] if isinstance(label, dict) else str(label))
                for label in issue.get("labels", [])
            }
        ]
        if labelled:
            candidates = labelled
        else:
            # The repository's labels have not been created yet
            # (PROJECT_STATE.md -> "Blocked"). Fall back to the issue
            # body, which is where the seeded tasks declare their state.
            self.log(
                f"note: no open issue carries the {READY_LABEL!r} label; falling back to "
                "reading task state from issue bodies. Run scripts/setup/create_labels.sh "
                "to enable label-based filtering."
            )
            candidates = [
                issue for issue in all_issues if (issue.get("state") or "open").lower() == "open"
            ]

        queue = TaskQueue([parse_issue(issue) for issue in candidates])
        return queue.ordered(), task_index

    def select_task(self, skip: set[int]) -> tuple[TaskSpec | None, str]:
        """The first eligible task, or why none is available."""
        tasks, task_index = self.fetch_candidates()
        reasons: list[str] = []
        for task in tasks:
            if task.issue_number in skip:
                continue
            comments = self.client.list_comments(task.issue_number)
            eligibility = check_eligibility(
                task,
                task_index=task_index,
                comments=comments,
                worker_id=self.config.worker_id,
            )
            if eligibility.eligible:
                return task, ""
            reasons.append(f"  #{task.issue_number} {eligibility.reason}")
        return None, "No eligible READY task.\n" + "\n".join(reasons)

    # -- the run ------------------------------------------------------
    def run(self) -> RunSummary:
        skip: set[int] = set()
        while True:
            stop = self.limits.stop_reason()
            if stop:
                self.summary.stop_reason = stop
                break

            task, reason = self.select_task(skip)
            if task is None:
                self.summary.stop_reason = reason
                break

            self.log(f"\n=== {task.task_id} (issue #{task.issue_number}) — {task.title}")
            attempt = self.attempt_task(task)
            self.summary.attempts.append(attempt)
            skip.add(task.issue_number)
            self.limits.record_task()

            if attempt.outcome in (Outcome.FAILED, Outcome.BLOCKED, Outcome.PROPOSAL):
                # A blocker, a failure, or a task awaiting authorization
                # all mean a human should look before more work lands.
                self.summary.stop_reason = (
                    f"{task.task_id} ended as {attempt.outcome}: {attempt.reason}"
                )
                break
        return self.summary

    def attempt_task(self, task: TaskSpec) -> TaskAttempt:
        run_id = new_run_id()
        started_at = datetime.now(timezone.utc).isoformat()

        # -- step 6/7: claim, then verify ---------------------------
        outcome = claim_protocol.claim_task(self.client, task, self.config.worker_id)
        if not outcome.won:
            self.log(f"LOST claim on {task.task_id}: {outcome.reason}")
            claim_protocol.withdraw_claim(
                self.client,
                task.issue_number,
                outcome.claim_id,
                self.config.worker_id,
                reason=outcome.reason,
            )
            return TaskAttempt(
                task.task_id, task.issue_number, Outcome.LOST_CLAIM, outcome.reason, run_id=run_id
            )
        self.log(f"WON claim on {task.task_id} (claim_id={outcome.claim_id})")
        self._set_labels(task.issue_number, add=["status:claimed"], remove=[READY_LABEL])

        # -- human authorization boundary ---------------------------
        if task.requires_human_execution:
            return self._stop_for_authorization(task, run_id, started_at)

        # -- step 8: isolated branch --------------------------------
        try:
            branch = self.git.create_branch(task.branch_name, base=self.config.base_branch)
        except GitError as error:
            return self._record_failure(task, run_id, started_at, "", f"branch creation failed: {error}")
        self.log(f"branch: {branch}")

        base_sha = "" if self.config.dry_run else self.git.head_sha()

        # What was already dirty before the AI ran. `create_branch`
        # refuses a dirty tree on a live run, so this is empty there; in a
        # rehearsal (or after an interrupted run) it stops the worker
        # attributing someone else's uncommitted files to the AI and
        # blocking the task for a scope violation it did not commit.
        pre_existing = set(self.git.changed_files())

        handoff = Handoff(
            run_id=run_id,
            worker_id=self.config.worker_id,
            task_id=task.task_id,
            issue_number=task.issue_number,
            branch=branch,
            started_at=started_at,
            goal=task.objective or task.title,
        )

        # -- step 9: bounded context --------------------------------
        pack = build_context(task, self.config.repo_root)
        handoff.context_included = list(pack.included)
        handoff.context_omitted = list(pack.omitted)
        self.log(f"context: {len(pack.included)} document(s), {pack.size} chars")

        # -- step 10: run the AI ------------------------------------
        provider = self.router.select(
            "claude-code-cli", reason=f"{task.task_id}:{task.task_type}:tier1-2-development"
        )
        handoff.routing_events = [event.render() for event in self.router.events]

        prompt = self._build_prompt(task, pack.render())
        try:
            result = self.adapter.execute(
                prompt,
                task_id=task.task_id,
                workdir=str(self.config.repo_root),
                timeout=int(os.environ.get("WORKER_AI_TIMEOUT", "3600")),
            )
            self._record_usage(provider, status="ok")
        except AdapterError as error:
            self._record_usage(provider, status="error", error=str(error))
            handoff.result = AIResult(
                task_id=task.task_id,
                status="FAILED",
                summary=f"The AI adapter failed: {error}",
                tests=SuiteResult(),
                known_issues=[str(error)],
                requires_human_review=True,
            )
            return self._finish_failed(task, handoff, f"adapter error: {error}")

        handoff.result = result
        self.log(f"AI reported: {result.status} — {result.summary[:120]}")

        # -- step 11a: scope enforcement ----------------------------
        guard = ScopeGuard(task.allowed_paths, task.forbidden_paths)
        changed = [
            path
            for path in self.git.changed_files(since=base_sha if base_sha else "")
            if path not in pre_existing
        ]
        report = guard.check(changed)
        if not report.ok:
            handoff.scope_violations = [
                f"`{violation.path}`: {violation.detail}" for violation in report.violations
            ]
            return self._stop_for_scope(task, handoff, report)

        if result.changed_files:
            declared = guard.check(list(result.changed_files))
            if not declared.ok:
                handoff.scope_violations = [
                    f"`{violation.path}` (reported by the AI): {violation.detail}"
                    for violation in declared.violations
                ]
                return self._stop_for_scope(task, handoff, declared)

        if not changed and result.status not in ("BLOCKED", "PROPOSAL"):
            handoff.notes.append(
                "The AI reported success but the working tree is unchanged."
            )

        handoff.result.changed_files = sorted(set(result.changed_files) | set(report.allowed))

        # -- step 11b: validation -----------------------------------
        validation = self.validator.run(changed_paths=report.allowed)
        handoff.validation_summary = validation.summary()
        handoff.validation_detail = validation.render()
        self.log(validation.summary())

        passed, failed, skipped = validation.pytest_counts()
        if passed or failed or skipped:
            handoff.result.tests = SuiteResult(
                passed=passed, failed=failed, skipped=skipped,
                details=validation.summary(),
            )

        # -- ADR / experiment escalation ----------------------------
        handoff.adr_required = requires_adr(handoff.result.changed_files)
        handoff.experiment_required = task.task_type == "experiment"

        blocked_by_ai = result.status == "BLOCKED"
        validation_ok = validation.ok and not blocked_by_ai
        # A PR only looks review-ready when something actually ran and
        # passed; "nothing was checked" gets a draft, same as a failure.
        validation_verified = validation.verified and not blocked_by_ai
        handoff.outcome = (
            Outcome.BLOCKED if blocked_by_ai
            else (Outcome.DONE if validation_ok else Outcome.FAILED)
        )
        handoff.finished_at = datetime.now(timezone.utc).isoformat()

        # -- steps 12/13: handoff + history -------------------------
        handoff.write(self.config.repo_root, dry_run=self.config.dry_run)
        append_timeline(self.config.repo_root, handoff=handoff, dry_run=self.config.dry_run)

        # -- step 14: commit, push, PR ------------------------------
        commit_message = self._commit_message(task, handoff)
        try:
            self.git.commit_all(commit_message)
            self.git.push(branch)
        except GitError as error:
            return self._record_failure(task, run_id, started_at, branch, f"push failed: {error}")

        draft = build_pull_request(
            task=task,
            handoff=handoff,
            validation_ok=validation_ok,
            validation_verified=validation_verified,
            base_branch=self.config.base_branch,
            adapter_name=getattr(self.adapter, "name", "unknown"),
        )
        pull = self.client.create_pull_request(
            title=draft.title, head=draft.head, base=draft.base, body=draft.body, draft=draft.draft
        )
        pr_url = (pull or {}).get("html_url", "") if isinstance(pull, dict) else ""
        handoff.pr_url = pr_url
        self.log(f"PR: {pr_url or '(dry run — not created)'}")

        # -- step 15: update the task's state -----------------------
        if validation_ok:
            self._set_labels(task.issue_number, add=["status:review"], remove=["status:claimed"])
        else:
            self._set_labels(task.issue_number, add=["status:blocked"], remove=["status:claimed"])
        self.client.add_comment(task.issue_number, self._issue_update(handoff, validation_ok))

        # -- after PR: merging is a human decision ------------------
        decision = merge_policy.evaluate(
            task=task,
            changed_paths=handoff.result.changed_files,
            allow_auto_merge=self.allow_auto_merge,
            ci_passed=False,  # CI has not reported yet on a just-opened PR
            requires_human_review=handoff.result.requires_human_review,
        )
        self.log(f"auto-merge: NO — {decision.reason}")

        return TaskAttempt(
            task_id=task.task_id,
            issue_number=task.issue_number,
            outcome=handoff.outcome,
            reason=handoff.validation_summary,
            branch=branch,
            pr_url=pr_url,
            run_id=run_id,
        )

    # -- prompt -------------------------------------------------------
    def _build_prompt(self, task: TaskSpec, context: str) -> str:
        return f"""You are a development worker for the TrueLock repository. You are
implementing exactly one task, and nothing else.

Working directory: {self.config.repo_root}
Worker: {self.config.worker_id}

{context}

## How to work

1. Implement the task inside the allowed paths. Nothing outside them.
2. Follow the repository's existing conventions -- read a neighbouring
   file before writing a new one.
3. Write or update tests for what you change (`docs/testing.md`).
4. Update the module README(s) your change makes out of date.
5. Do not run destructive commands: no force push, no branch deletion,
   no history rewriting, no changes to secrets, permissions, or branch
   protection. Do not merge anything.
6. Do not commit; the worker commits for you.
7. If the task cannot be done within the allowed paths, stop and return
   status "BLOCKED" naming what is missing. That is a correct outcome,
   not a failure.

## Required output

End your response with a single JSON object in a ```json fenced block,
and nothing after it:

```json
{{
  "task_id": "{task.task_id}",
  "status": "DONE | PARTIAL | BLOCKED | FAILED",
  "summary": "what you actually did, in two or three sentences",
  "changed_files": ["path/one.py"],
  "tests": {{"passed": 0, "failed": 0, "skipped": 0, "details": "what you ran"}},
  "new_dependencies": [],
  "known_issues": [],
  "documentation_changes": [],
  "next_recommended_tasks": [],
  "requires_human_review": false
}}
```

Report what is true, not what would look good. An honest BLOCKED or
PARTIAL is more useful to the next worker than an optimistic DONE.
"""

    # -- outcome helpers ---------------------------------------------
    def _commit_message(self, task: TaskSpec, handoff: Handoff) -> str:
        summary = (handoff.result.summary if handoff.result else "").strip().splitlines()
        headline = summary[0] if summary else "automated task execution"
        if len(headline) > 68:
            headline = headline[:65].rstrip() + "..."
        return (
            f"{task.task_id}: {headline}\n\n"
            f"Worker: {self.config.worker_id}\n"
            f"Run: {handoff.run_id}\n"
            f"Issue: #{task.issue_number}\n"
            f"Validation: {handoff.validation_summary or 'not run'}\n"
        )

    def _issue_update(self, handoff: Handoff, validation_ok: bool) -> str:
        verdict = "validation passed" if validation_ok else "**VALIDATION FAILED**"
        return (
            f"WORKER UPDATE\n"
            f"worker_id: {handoff.worker_id}\n"
            f"run_id: {handoff.run_id}\n"
            f"branch: {handoff.branch}\n"
            f"result: {handoff.outcome} ({verdict})\n"
            f"pull_request: {handoff.pr_url or 'not created'}\n"
            f"history: history/ai-activity/{handoff.history_filename()}\n\n"
            f"{handoff.validation_summary}\n\n"
            "This PR is not auto-merged. A human decides (CONTRIBUTING.md §5)."
        )

    def _set_labels(self, issue_number: int, *, add: list[str], remove: list[str]) -> None:
        """Best-effort label updates.

        The repository's labels do not exist yet (`PROJECT_STATE.md` ->
        "Blocked"), so a 404 here is expected and must not abort a run.
        The claim comments remain the authoritative record either way.
        """
        for label in add:
            try:
                self.client.add_labels(issue_number, [label])
            except Exception as error:  # noqa: BLE001 - label state is advisory
                self.log(f"note: could not add label {label!r} ({error}); continuing")
        for label in remove:
            try:
                self.client.remove_label(issue_number, label)
            except Exception as error:  # noqa: BLE001
                self.log(f"note: could not remove label {label!r} ({error}); continuing")

    def _record_usage(self, provider, *, status: str, error: str | None = None) -> None:
        usage = getattr(self.adapter, "last_usage", None)
        self.ledger.record(
            provider=provider.provider,
            project=provider.id,
            model=getattr(self.adapter, "model", "") or self.config.model or "default",
            status=status,
            request_id=getattr(usage, "request_id", "") or "",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cached_tokens=getattr(usage, "cached_tokens", None),
            estimated_cost=getattr(usage, "estimated_cost", None),
            error=error,
        )

    def _stop_for_authorization(self, task: TaskSpec, run_id: str, started_at: str) -> TaskAttempt:
        """`execution:human`: propose, do not implement."""
        self.log(f"{task.task_id} is execution:human — producing a proposal, writing no code.")
        proposal = build_human_authorization_proposal(task, worker_id=self.config.worker_id)
        self.client.add_comment(task.issue_number, proposal)
        self._set_labels(task.issue_number, add=["status:blocked"], remove=["status:claimed"])
        claim_protocol.release_task(
            self.client,
            task.issue_number,
            self.config.worker_id,
            reason="execution:human — task returned to the queue pending authorization",
        )

        handoff = Handoff(
            run_id=run_id,
            worker_id=self.config.worker_id,
            task_id=task.task_id,
            issue_number=task.issue_number,
            branch="(none — no code was written)",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            goal=task.objective or task.title,
            outcome=Outcome.PROPOSAL,
            result=AIResult(
                task_id=task.task_id,
                status="PROPOSAL",
                summary=(
                    "Task requires human authorization (CONTRIBUTING.md §5). The "
                    "worker posted a proposal on the issue and made no code changes."
                ),
                requires_human_review=True,
            ),
            notes=["No branch created, no file modified: the authorization boundary held."],
        )
        handoff.write(self.config.repo_root, dry_run=self.config.dry_run)
        return TaskAttempt(
            task.task_id,
            task.issue_number,
            Outcome.PROPOSAL,
            "requires human authorization; proposal posted",
            run_id=run_id,
        )

    def _stop_for_scope(self, task: TaskSpec, handoff: Handoff, report) -> TaskAttempt:
        """Out-of-scope change: stop, mark BLOCKED, explain. Never widen."""
        self.log("SCOPE VIOLATION — stopping without a PR")
        handoff.outcome = Outcome.BLOCKED
        handoff.finished_at = datetime.now(timezone.utc).isoformat()
        if handoff.result is not None:
            handoff.result.requires_human_review = True
        handoff.write(self.config.repo_root, dry_run=self.config.dry_run)

        missing = ", ".join(sorted({violation.path.split("/")[0] for violation in report.violations}))
        body = (
            f"BLOCKED — scope\n"
            f"worker_id: {self.config.worker_id}\n"
            f"run_id: {handoff.run_id}\n"
            f"branch: {handoff.branch} (pushed for inspection, no PR opened)\n\n"
            f"{report.render()}\n\n"
            f"This task's `allowed_paths` do not cover `{missing}`. The worker "
            "stopped rather than widening its own scope (CONTRIBUTING.md §4).\n\n"
            "To unblock, a human should either extend `allowed_paths` on this "
            "task, or split the work out into a task that owns those paths and "
            "add it to this task's `depends_on`."
        )
        self.client.add_comment(task.issue_number, body)
        self._set_labels(task.issue_number, add=["status:blocked"], remove=["status:claimed"])

        try:
            self.git.commit_all(
                f"{task.task_id}: WIP — stopped for scope violation (no PR)\n\n"
                f"Worker: {self.config.worker_id}\nRun: {handoff.run_id}\n"
            )
            self.git.push(handoff.branch)
        except GitError as error:
            self.log(f"note: could not push the blocked branch ({error})")

        return TaskAttempt(
            task.task_id,
            task.issue_number,
            Outcome.BLOCKED,
            f"scope violation: {report.violations[0].detail}",
            branch=handoff.branch,
            run_id=handoff.run_id,
        )

    def _finish_failed(self, task: TaskSpec, handoff: Handoff, reason: str) -> TaskAttempt:
        handoff.outcome = Outcome.FAILED
        handoff.finished_at = datetime.now(timezone.utc).isoformat()
        handoff.write(self.config.repo_root, dry_run=self.config.dry_run)
        append_timeline(self.config.repo_root, handoff=handoff, dry_run=self.config.dry_run)
        self.client.add_comment(
            task.issue_number,
            f"WORKER FAILED\nworker_id: {self.config.worker_id}\n"
            f"run_id: {handoff.run_id}\nbranch: {handoff.branch}\n\n{reason}\n\n"
            "No pull request was opened. See "
            f"`history/ai-activity/{handoff.history_filename()}`.",
        )
        self._set_labels(task.issue_number, add=["status:blocked"], remove=["status:claimed"])
        claim_protocol.release_task(
            self.client, task.issue_number, self.config.worker_id, reason=reason
        )
        return TaskAttempt(
            task.task_id, task.issue_number, Outcome.FAILED, reason,
            branch=handoff.branch, run_id=handoff.run_id,
        )

    def _record_failure(
        self, task: TaskSpec, run_id: str, started_at: str, branch: str, reason: str
    ) -> TaskAttempt:
        handoff = Handoff(
            run_id=run_id,
            worker_id=self.config.worker_id,
            task_id=task.task_id,
            issue_number=task.issue_number,
            branch=branch or "(none)",
            started_at=started_at,
            goal=task.objective or task.title,
            result=AIResult(
                task_id=task.task_id, status="FAILED", summary=reason,
                known_issues=[reason], requires_human_review=True,
            ),
        )
        return self._finish_failed(task, handoff, reason)
