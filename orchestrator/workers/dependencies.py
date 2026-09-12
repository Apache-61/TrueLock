"""Is this task actually safe to start?

A task is eligible only when *all* of these hold (the worker refuses on
the first failure and says which one):

* it is READY;
* it is authorized -- not WAITING_AUTHORIZATION, not RESEARCH/PROPOSAL;
* every task in `depends_on` is MERGED or VERIFIED;
* it is not BLOCKED;
* no other worker holds a live claim on it.

The dependency check is deliberately conservative: a dependency whose
state cannot be determined counts as *unsatisfied*. Building on top of a
task that might not have merged produces a PR that cannot be reviewed
honestly, which costs far more than waiting.
"""
from __future__ import annotations

from dataclasses import dataclass

from .claim import find_winning_claim
from .tasks import TaskSpec, parse_issue

#: States that mean the dependency's work is really in `main`.
SATISFIED_STATES = {"MERGED", "VERIFIED"}

#: Issue labels that assert the same thing.
SATISFIED_LABELS = {"status:done"}

#: States from which a worker must never start implementing.
UNAUTHORIZED_STATES = {"RESEARCH", "PROPOSAL", "WAITING_AUTHORIZATION"}

TERMINAL_STATES = {"BLOCKED", "REJECTED", "CANCELLED"}


@dataclass(frozen=True)
class Eligibility:
    """Why a task may or may not be started."""

    eligible: bool
    reason: str
    unmet_dependencies: tuple[str, ...] = ()
    blocking_worker: str = ""

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.eligible


def _dependency_is_satisfied(issue: dict | None) -> bool:
    if issue is None:
        return False
    if (issue.get("state") or "").lower() == "closed":
        return True
    labels = {
        (label["name"] if isinstance(label, dict) else str(label))
        for label in issue.get("labels", [])
    }
    if labels & SATISFIED_LABELS:
        return True
    return parse_issue(issue).status in SATISFIED_STATES


def build_task_index(issues: list[dict]) -> dict[str, dict]:
    """Map TASK-### -> issue payload, for dependency resolution."""
    index: dict[str, dict] = {}
    for issue in issues:
        spec = parse_issue(issue)
        index.setdefault(spec.task_id, issue)
    return index


def check_eligibility(
    task: TaskSpec,
    *,
    task_index: dict[str, dict],
    comments: list[dict] | None = None,
    worker_id: str = "",
    claim_stale_minutes: float = 0.0,
) -> Eligibility:
    """Apply every gate, in the order that fails cheapest first."""
    if task.issue_state == "closed":
        return Eligibility(False, f"{task.task_id}: issue is closed")

    if task.status in TERMINAL_STATES:
        return Eligibility(False, f"{task.task_id}: status is {task.status}")

    if task.status in UNAUTHORIZED_STATES:
        return Eligibility(
            False,
            f"{task.task_id}: status is {task.status}, which is not authorized "
            "for execution (CONTRIBUTING.md 5)",
        )

    if task.status not in {"READY", "CLAIMED"}:
        return Eligibility(
            False, f"{task.task_id}: status is {task.status}, expected READY"
        )

    unmet = tuple(
        dependency
        for dependency in task.depends_on
        if not _dependency_is_satisfied(task_index.get(dependency))
    )
    if unmet:
        known = ", ".join(
            f"{dependency}"
            + ("" if dependency in task_index else " (no matching issue found)")
            for dependency in unmet
        )
        return Eligibility(
            False,
            f"{task.task_id}: unmet dependencies -- {known}. A dependency counts "
            "as satisfied only when its issue is closed or labelled status:done "
            "(MERGED/VERIFIED).",
            unmet_dependencies=unmet,
        )

    if comments is not None:
        winner = find_winning_claim(comments, stale_after_minutes=claim_stale_minutes)
        if winner is not None and winner.worker_id != worker_id:
            return Eligibility(
                False,
                f"{task.task_id}: already claimed by {winner.worker_id} "
                f"(claim_id={winner.claim_id})",
                blocking_worker=winner.worker_id,
            )

    return Eligibility(True, f"{task.task_id}: eligible")
