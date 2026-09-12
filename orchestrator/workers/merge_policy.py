"""What may never be merged without a human.

TASK-007's first acceptance criterion is flat: "Never auto-merges." This
module is how that is enforced rather than remembered.

The worker's default is to never merge anything. Auto-merge requires
*three* independent conditions, all of which must hold:

1. the human running the worker passed `--allow-auto-merge` on the
   command line -- an explicit, per-invocation authorization;
2. the task issue carries the `execution:auto-merge-approved` marker,
   applied by a human beforehand;
3. the change is in none of the categories below.

Categories that are refused even when 1 and 2 hold, because
CONTRIBUTING.md 5 reserves them for a human regardless of who asked:
architecture, contracts and schemas, security, database migrations,
CI/CD and repository governance.

If you are reading this because you want the worker to merge something:
the answer is to have a human merge it. That is not friction, it is the
review step the whole PR protocol exists to create.
"""
from __future__ import annotations

from dataclasses import dataclass

from .scope import repo_relative

#: Marker a human applies to a task issue to pre-authorize auto-merge.
AUTO_MERGE_MARKER = "execution:auto-merge-approved"

#: path prefix -> why a human must look at it.
HUMAN_ONLY_PATHS: tuple[tuple[str, str], ...] = (
    ("ARCHITECTURE.md", "architecture change (CONTRIBUTING.md 5)"),
    ("DECISIONS.md", "recorded decision"),
    ("SECURITY.md", "security policy (CONTRIBUTING.md 5)"),
    ("docs/contracts/", "domain contract (CONTRIBUTING.md 5)"),
    ("domain/schemas/", "frozen JSON Schema contract (CONTRIBUTING.md 5)"),
    ("database/migrations/", "database migration (CONTRIBUTING.md 5)"),
    ("history/decisions/", "architecture decision record"),
    (".github/", "repository governance / CI configuration"),
    (".gitignore", "repository governance"),
    ("scripts/setup/", "repository administration"),
    ("orchestrator/policies/", "budget and provider policy"),
)

#: Task types that are never simple enough to merge unattended.
HUMAN_ONLY_TYPES = {"security", "decision", "experiment", "research"}


@dataclass(frozen=True)
class MergeDecision:
    """Whether this PR may be auto-merged, and the reason either way."""

    allowed: bool
    reason: str

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.allowed


def classify_paths(paths: list[str]) -> list[str]:
    """Reasons, if any, why these paths require a human merge."""
    reasons: list[str] = []
    for path in paths:
        normalized = repo_relative(path)
        for prefix, reason in HUMAN_ONLY_PATHS:
            if normalized == prefix or normalized.startswith(prefix):
                if reason not in reasons:
                    reasons.append(f"{reason} -- `{normalized}`")
    return reasons


def evaluate(
    *,
    task,
    changed_paths: list[str],
    allow_auto_merge: bool,
    ci_passed: bool,
    requires_human_review: bool,
) -> MergeDecision:
    """Apply every gate. The default answer is no."""
    if not allow_auto_merge:
        return MergeDecision(
            False,
            "auto-merge is off by default; this worker leaves every PR for a "
            "human (TASK-007 acceptance criterion, CONTRIBUTING.md 5)",
        )
    if AUTO_MERGE_MARKER not in set(getattr(task, "labels", ())):
        return MergeDecision(
            False,
            f"the task issue does not carry the {AUTO_MERGE_MARKER} marker, so "
            "no human pre-authorized unattended merging of this task",
        )
    if getattr(task, "task_type", "") in HUMAN_ONLY_TYPES:
        return MergeDecision(
            False, f"task type {task.task_type!r} always requires a human merge"
        )
    if requires_human_review:
        return MergeDecision(False, "the AI flagged requires_human_review")
    if not ci_passed:
        return MergeDecision(False, "CI has not reported success on this PR")
    path_reasons = classify_paths(changed_paths)
    if path_reasons:
        return MergeDecision(False, "; ".join(path_reasons))
    return MergeDecision(
        True,
        "pre-authorized simple task, CI green, no human-only path touched",
    )
