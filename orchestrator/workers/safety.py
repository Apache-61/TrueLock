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


@dataclass
class RunLimits:
    """Bounds on one `worker start` run."""

    max_tasks: int = 0            # 0 == unlimited (but --once still stops at 1)
    max_runtime_minutes: float = 0.0
    once: bool = False
    dry_run: bool = False
    started_at: float = field(default_factory=time.monotonic)
    tasks_completed: int = 0

    def start(self) -> "RunLimits":
        self.started_at = time.monotonic()
        return self

    @property
    def elapsed_minutes(self) -> float:
        return (time.monotonic() - self.started_at) / 60.0

    def record_task(self) -> None:
        self.tasks_completed += 1

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
        return ""

    def should_continue(self) -> bool:
        return not self.stop_reason()
