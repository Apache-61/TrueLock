"""Run limits and the things a worker must never do.

Two separate mechanisms live here:

`RunLimits`    bounds on the *run*: how many tasks, how long, dry-run.
               A loop that can run forever on a machine nobody is
               watching is a loop that will.
`is_destructive` a refusal list for shell commands. The worker runs
               commands on behalf of an AI; this is the boundary that
               says which ones it declines regardless of who asked.

The refusal list is derived directly from the operating constraints:
never delete other people's branches, never delete data, never touch
secrets, GitHub permissions, or branch protection, never change
architecture silently.

This is a guard rail, not a sandbox. It catches the obvious and the
accidental. Real isolation is the workstation's job -- which is why
`docs/orchestration/worker-setup.md` says to run the worker in a
dedicated clone.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

#: (pattern, why). Matched case-insensitively against the whole command.
DESTRUCTIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\brm\s+(-[a-z]*\s+)*-[a-z]*[rf]", "recursive/forced delete"),
    (r"\bgit\s+push\b.*(--force\b|-f\b|\+)", "force push overwrites other people's commits"),
    (r"\bgit\s+push\b.*--delete\b", "deleting a remote branch"),
    (r"\bgit\s+branch\s+(-D|-d|--delete)\b", "deleting a branch"),
    (r"\bgit\s+reset\s+--hard\b", "discards uncommitted work"),
    (r"\bgit\s+clean\b.*-[a-z]*[fx]", "deletes untracked and ignored files"),
    (r"\bgit\s+filter-(branch|repo)\b", "rewrites history"),
    (r"\bgh\s+repo\s+delete\b", "deletes a repository"),
    (r"\bgh\s+(secret|variable)\s+(set|delete|remove)\b", "modifies repository secrets"),
    (r"\bgh\s+api\b.*/branches/.*/protection", "modifies branch protection"),
    (r"\bgh\s+api\b.*(/collaborators|/teams|/permissions)", "modifies repository permissions"),
    (r"\bgh\s+pr\s+merge\b", "merging is a human decision (CONTRIBUTING.md 5)"),
    (r"\bgit\s+merge\b.*\bmain\b.*--no-ff.*origin", "merging into main"),
    (r"\bdrop\s+(database|table|schema)\b", "destroys data"),
    (r"\btruncate\s+table\b", "destroys data"),
    (r"\b(mkfs|fdisk|dd)\s+", "destroys a filesystem or device"),
    (r":\s*\(\s*\)\s*\{.*\}\s*;\s*:", "fork bomb"),
    (r"\bchmod\s+(-R\s+)?777\b", "removes file permission boundaries"),
    (r"\bcurl\b.*\|\s*(ba)?sh\b", "executes unreviewed remote code"),
    (r"\bwget\b.*\|\s*(ba)?sh\b", "executes unreviewed remote code"),
    (r"\bhistory\s+-c\b", "erases the audit trail"),
)

_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), reason) for pattern, reason in DESTRUCTIVE_PATTERNS)


def is_destructive(command: str) -> tuple[bool, str]:
    """Would this command do something the worker is not authorized to do?"""
    text = " ".join(str(command).split())
    for pattern, reason in _COMPILED:
        if pattern.search(text):
            return True, reason
    return False, ""


class SafetyRefusal(RuntimeError):
    """A command or action was refused for safety."""


def assert_safe(command: str) -> None:
    destructive, reason = is_destructive(command)
    if destructive:
        raise SafetyRefusal(
            f"refusing to run {command!r}: {reason}. Destructive operations "
            "need explicit human authorization -- see CONTRIBUTING.md 5."
        )


#: Consecutive failed attempts after which a continuous worker stops.
#: A worker that keeps failing is usually broken in a way more attempts
#: will not fix -- a missing dependency, a bad token, a full disk -- and
#: an unattended loop that retries through it burns budget and fills the
#: queue with failure comments. Unrelated tasks failing in a row is
#: itself the signal that the machine, not the task, is at fault.
DEFAULT_FAILURE_STREAK = 3


@dataclass
class RunLimits:
    """Bounds on one `worker start` run.

    A loop that can run forever on a machine nobody is watching is a loop
    that will. Every way this one ends is named here, so `worker start
    --continuous` always has an answer to "why did it stop".
    """

    max_tasks: int = 0            # 0 == unlimited (but --once still stops at 1)
    max_runtime_minutes: float = 0.0
    once: bool = False
    dry_run: bool = False
    #: Wall-clock ceiling on waiting for new work to become eligible.
    #: 0 == wait indefinitely (the normal mode for an attended machine).
    max_idle_minutes: float = 0.0
    max_failure_streak: int = DEFAULT_FAILURE_STREAK
    #: Continuous mode only. When the queue has nothing eligible, wait and
    #: re-read instead of exiting: on a 55-task graph most tasks become
    #: eligible only when a human merges the PR they depend on, which
    #: happens on someone else's clock, not this loop's.
    poll_when_idle: bool = False
    #: A BLOCKED or PROPOSAL outcome ends the run. True keeps the original
    #: `--once` behaviour -- a human looks before more work piles up. A
    #: continuous worker sets this False: those outcomes are expected and
    #: self-documenting on the issue, and idling a whole machine for one
    #: of them wastes a quarter of the team's capacity.
    stop_on_blocker: bool = True
    started_at: float = field(default_factory=time.monotonic)
    tasks_completed: int = 0
    idle_since: float | None = None
    failure_streak: int = 0

    def start(self) -> "RunLimits":
        self.started_at = time.monotonic()
        return self

    @property
    def elapsed_minutes(self) -> float:
        return (time.monotonic() - self.started_at) / 60.0

    @property
    def idle_minutes(self) -> float:
        if self.idle_since is None:
            return 0.0
        return (time.monotonic() - self.idle_since) / 60.0

    def record_task(self) -> None:
        self.tasks_completed += 1

    def record_outcome(self, *, failed: bool) -> None:
        """Track consecutive failures, so a broken machine gives up."""
        self.failure_streak = self.failure_streak + 1 if failed else 0

    def record_idle(self) -> None:
        """Mark that a poll found no eligible work."""
        if self.idle_since is None:
            self.idle_since = time.monotonic()

    def record_progress(self) -> None:
        """Work was found; the idle clock restarts from zero."""
        self.idle_since = None

    def stop_reason(self) -> str:
        """Why the loop must stop now, or "" to continue."""
        if self.once and self.tasks_completed >= 1:
            return "--once: one task attempted"
        if self.max_tasks and self.tasks_completed >= self.max_tasks:
            return f"--max-tasks {self.max_tasks} reached"
        if self.max_runtime_minutes and self.elapsed_minutes >= self.max_runtime_minutes:
            return (
                f"--max-runtime {self.max_runtime_minutes:g} minutes reached "
                f"({self.elapsed_minutes:.1f} elapsed)"
            )
        if self.max_failure_streak and self.failure_streak >= self.max_failure_streak:
            return (
                f"{self.failure_streak} task attempts failed in a row; stopping so a "
                "human can look. Unrelated tasks failing consecutively usually means "
                "this machine is misconfigured, not that the tasks are bad."
            )
        if self.max_idle_minutes and self.idle_minutes >= self.max_idle_minutes:
            return (
                f"--max-idle {self.max_idle_minutes:g} minutes with no eligible task "
                f"({self.idle_minutes:.1f} elapsed idle)"
            )
        return ""

    def should_continue(self) -> bool:
        return not self.stop_reason()
