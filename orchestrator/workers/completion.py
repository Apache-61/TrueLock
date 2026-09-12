"""Steps 14-17: verify, complete, and unlock what was waiting.

The worker opens a pull request and stops there (ADR-0005: a human
merges). Nothing then closed the task's issue -- and
`dependencies.check_eligibility` only counts a dependency as satisfied
when its issue is **closed or labelled `status:done`**.

So the queue stalled. A human merging TASK-001's PR did not make
TASK-002, TASK-003, TASK-008 or TASK-012 eligible, because the issue
stayed open. With a 55-task graph that is 7 merges deep, four machines
would have run out of claimable work after the first wave and sat idle
reporting "no eligible task" -- while the work they were waiting for was
already in `main`.

This module closes that loop. It reads the *outcome a human already
decided* and records it:

* PR merged   -> label `status:done`, close the issue, comment. Every
                 task depending on it becomes eligible on the next poll.
* PR closed   -> release the claim and return the task to the queue, so
  unmerged      the next worker can pick it up rather than it being
                 stranded behind a dead claim.

It never merges anything and never decides that work is acceptable. The
merge is the human's decision; this only propagates it. That distinction
is the whole reason it is safe to run unattended.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import claim as claim_protocol
from .tasks import TaskSpec

#: Marker comment, so a second pass over an already-completed task is a
#: no-op instead of a duplicate comment on every poll.
COMPLETION_MARKER = "TASK-COMPLETE"
REOPENED_MARKER = "TASK-RETURNED-TO-QUEUE"


@dataclass
class ReconcileResult:
    """What one reconciliation pass changed."""

    completed: list[str] = field(default_factory=list)
    returned: list[str] = field(default_factory=list)
    checked: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.completed or self.returned)

    def render(self) -> str:
        if not self.changed:
            return f"reconcile: {self.checked} task(s) checked, nothing to update"
        parts = []
        if self.completed:
            parts.append(f"completed {', '.join(self.completed)}")
        if self.returned:
            parts.append(f"returned to queue {', '.join(self.returned)}")
        return f"reconcile: {'; '.join(parts)}"


def _has_marker(comments: list[dict], marker: str) -> bool:
    return any(marker in (comment.get("body") or "") for comment in comments)


def find_pull_request(client, task: TaskSpec) -> dict | None:
    """The PR opened for this task's branch, merged or not.

    Matched by head branch rather than by parsing the worker's comment:
    the branch name is derived from the task id, so it still matches a PR
    a human opened or renamed.
    """
    try:
        pulls = client.list_pull_requests(state="all", head=task.branch_name)
    except Exception:  # noqa: BLE001 - a listing failure must not stop the loop
        return None
    if not pulls:
        return None
    # Newest first: a re-opened task may have more than one PR on the
    # same branch, and the latest is the one that decided its fate.
    return sorted(pulls, key=lambda pull: pull.get("number", 0))[-1]


def _is_merged(pull: dict) -> bool:
    if pull.get("merged") or pull.get("merged_at"):
        return True
    return False


def reconcile_task(client, task: TaskSpec, *, worker_id: str, log=print) -> str:
    """Bring one task's issue into line with its pull request.

    Returns "completed", "returned", or "" when nothing changed.
    """
    pull = find_pull_request(client, task)
    if pull is None:
        return ""

    state = (pull.get("state") or "").lower()
    comments = client.list_comments(task.issue_number)

    if _is_merged(pull):
        if _has_marker(comments, COMPLETION_MARKER):
            return ""
        log(f"{task.task_id}: PR #{pull.get('number')} is merged — closing the issue")
        client.add_comment(
            task.issue_number,
            f"{COMPLETION_MARKER}\n"
            f"worker_id: {worker_id}\n"
            f"pull_request: {pull.get('html_url', '')}\n"
            f"timestamp: {claim_protocol.utc_now()}\n\n"
            "The pull request for this task has been merged by a human. Closing the "
            "issue so that every task depending on it becomes eligible "
            "(`orchestrator/workers/dependencies.py`).\n\n"
            "The worker did not merge this and did not judge it acceptable -- it is "
            "recording a decision that was already made.",
        )
        _safe_labels(client, task.issue_number, add=["status:done"],
                     remove=["status:review", "status:claimed", "status:ready"], log=log)
        try:
            client.update_issue(task.issue_number, state="closed")
        except Exception as error:  # noqa: BLE001
            log(f"note: could not close issue #{task.issue_number} ({error}); "
                "the status:done label still satisfies the dependency check")
        return "completed"

    if state == "closed":
        # Closed without merging: the work was rejected or abandoned. The
        # claim must not outlive it, or the task is stranded.
        if _has_marker(comments, REOPENED_MARKER):
            return ""
        log(f"{task.task_id}: PR #{pull.get('number')} was closed unmerged — returning to the queue")
        client.add_comment(
            task.issue_number,
            f"{REOPENED_MARKER}\n"
            f"worker_id: {worker_id}\n"
            f"pull_request: {pull.get('html_url', '')}\n"
            f"timestamp: {claim_protocol.utc_now()}\n\n"
            "The pull request for this task was closed without being merged, so the "
            "task is not done. Releasing the claim and returning it to the queue.",
        )
        claim_protocol.release_task(
            client,
            task.issue_number,
            worker_id,
            reason="pull request closed without merging",
        )
        _safe_labels(client, task.issue_number, add=["status:ready"],
                     remove=["status:review", "status:claimed"], log=log)
        return "returned"

    return ""


def _safe_labels(client, issue_number: int, *, add: list[str], remove: list[str], log) -> None:
    """Label updates are advisory; closing the issue is what matters."""
    for label in add:
        try:
            client.add_labels(issue_number, [label])
        except Exception as error:  # noqa: BLE001
            log(f"note: could not add label {label!r} ({error}); continuing")
    for label in remove:
        try:
            client.remove_label(issue_number, label)
        except Exception:  # noqa: BLE001, S110 - absent label is not an error
            pass


def reconcile(client, tasks: list[TaskSpec], *, worker_id: str, log=print) -> ReconcileResult:
    """Reconcile every task that could plausibly have a finished PR.

    Only tasks the worker has already taken somewhere are checked -- a
    READY task with no claim has no PR, and probing each one would cost a
    request per task per poll.
    """
    result = ReconcileResult()
    for task in tasks:
        if task.status not in ("READY_FOR_REVIEW", "CLAIMED", "IN_PROGRESS", "TESTING", "BLOCKED"):
            continue
        result.checked += 1
        outcome = reconcile_task(client, task, worker_id=worker_id, log=log)
        if outcome == "completed":
            result.completed.append(task.task_id)
        elif outcome == "returned":
            result.returned.append(task.task_id)
    return result
