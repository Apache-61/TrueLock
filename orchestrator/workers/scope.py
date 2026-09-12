"""allowed_paths / forbidden_paths enforcement.

CONTRIBUTING.md 4 gives every task a path budget, and 6 makes
"nothing else changed" part of the definition of done. This module is
what makes that checkable instead of aspirational.

Design rules, in priority order:

1. **Forbidden wins over allowed.** If a path matches both lists, it is
   forbidden. Overlap is a spec mistake, and the safe reading of a
   mistake is the restrictive one.
2. **An empty `allowed_paths` allows nothing.** A task that forgot to
   declare its paths is a task the worker must not act on -- defaulting
   to "anything" would turn a drafting slip into an unbounded diff.
3. **Escapes are violations.** `../`, absolute paths, and symlinked
   escapes never match an allowed glob, whatever the glob says.

When a task genuinely needs a path it was not granted, the worker does
not widen the scope: it stops, marks the task BLOCKED, and reports the
missing dependency, per the operating rule "no ampliar silenciosamente
el scope".
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field

#: Paths the worker writes as part of its own bookkeeping, never as part
#: of implementing the task. They are exempt from the task's path budget
#: because they exist *because of* the process, not the change: the
#: handoff record, the task mirror, and the timeline are required of
#: every task by CONTRIBUTING.md 6.
BOOKKEEPING_PATHS = (
    "history/ai-activity/**",
    "history/timeline.md",
    "tasks/ready/**",
    "tasks/active/**",
    "tasks/blocked/**",
    "tasks/completed/**",
    # Worker runtime state: the usage ledger and local scratch. `.gitignore`
    # already keeps these out of commits in this repository, but the scope
    # verdict must not depend on a consumer repo's ignore rules -- the
    # worker's own ledger is never part of the task's diff.
    ".state/**",
    "orchestrator/state/**",
)


def _strip_leading_dot_slash(value: str) -> str:
    """Remove a leading `./` -- and nothing else.

    Not `lstrip("./")`: that strips *characters*, so `.github/...`
    becomes `github/...` and every rule keyed on `.github/` stops
    matching. A silently non-matching safety rule is worse than none.
    """
    while value.startswith("./"):
        value = value[2:]
    return value


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a git-style path glob into a regex.

    `**` crosses directory separators, `*` and `?` do not. A pattern
    ending in `/` or naming a bare directory matches everything beneath
    it, which is how the task files are written in practice
    (`orchestrator/workers/**` and `orchestrator/workers/` mean the same
    thing to a reader, so they must mean the same thing here).
    """
    pattern = _strip_leading_dot_slash(pattern.strip())
    if not pattern:
        return re.compile(r"(?!)")  # matches nothing
    if pattern.endswith("/"):
        pattern += "**"

    out = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append(r"(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(r".*")
            index += 2
        elif char == "*":
            out.append(r"[^/]*")
            index += 1
        elif char == "?":
            out.append(r"[^/]")
            index += 1
        else:
            out.append(re.escape(char))
            index += 1
    # A bare directory name covers its contents.
    out.append(r"(?:/.*)?$")
    return re.compile("".join(out))


def repo_relative(path: str) -> str:
    """Normalize a path for prefix comparisons, preserving a leading dot."""
    return _strip_leading_dot_slash(str(path).replace("\\", "/").strip())


def normalize(path: str) -> str:
    """Repository-relative, forward-slashed, with no `.`/`..` segments.

    Returns "" for anything that escapes the repository root, so callers
    can treat "" as "never matches".
    """
    candidate = repo_relative(path)
    if not candidate or candidate.startswith("/"):
        return ""
    candidate = posixpath.normpath(candidate)
    if candidate in (".", "..") or candidate.startswith("../"):
        return ""
    return candidate


def matches_any(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    normalized = normalize(path)
    if not normalized:
        return False
    return any(_glob_to_regex(pattern).match(normalized) for pattern in patterns)


@dataclass
class ScopeViolation:
    """One changed path the task was not authorized to touch."""

    path: str
    rule: str  # "forbidden" | "not-allowed" | "escape"
    detail: str


@dataclass
class ScopeReport:
    """Verdict over a whole changed-file set."""

    allowed: list[str] = field(default_factory=list)
    violations: list[ScopeViolation] = field(default_factory=list)
    bookkeeping: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def render(self) -> str:
        if self.ok:
            return "All changed paths are inside the task's allowed_paths."
        lines = ["Scope violation -- these paths are outside the task's budget:"]
        for violation in self.violations:
            lines.append(f"  - `{violation.path}` : {violation.detail}")
        return "\n".join(lines)


class ScopeGuard:
    """Checks changed paths against one task's declared path budget."""

    def __init__(
        self,
        allowed_paths: tuple[str, ...] | list[str],
        forbidden_paths: tuple[str, ...] | list[str] = (),
        *,
        bookkeeping_paths: tuple[str, ...] = BOOKKEEPING_PATHS,
    ) -> None:
        self.allowed_paths = tuple(allowed_paths)
        self.forbidden_paths = tuple(forbidden_paths)
        self.bookkeeping_paths = tuple(bookkeeping_paths)

    def classify(self, path: str) -> ScopeViolation | None:
        normalized = normalize(path)
        if not normalized:
            return ScopeViolation(
                path=str(path),
                rule="escape",
                detail="path escapes the repository root or is absolute",
            )
        if matches_any(normalized, self.forbidden_paths):
            return ScopeViolation(
                path=normalized,
                rule="forbidden",
                detail="matches the task's forbidden_paths",
            )
        if not self.allowed_paths:
            return ScopeViolation(
                path=normalized,
                rule="not-allowed",
                detail="the task declares no allowed_paths, so no file may be changed",
            )
        if not matches_any(normalized, self.allowed_paths):
            return ScopeViolation(
                path=normalized,
                rule="not-allowed",
                detail=(
                    "outside allowed_paths ("
                    + ", ".join(self.allowed_paths)
                    + ")"
                ),
            )
        return None

    def check(self, paths: list[str], *, allow_bookkeeping: bool = True) -> ScopeReport:
        report = ScopeReport()
        for path in paths:
            normalized = normalize(path)
            if allow_bookkeeping and normalized and matches_any(normalized, self.bookkeeping_paths):
                report.bookkeeping.append(normalized)
                continue
            violation = self.classify(path)
            if violation is None:
                report.allowed.append(normalized)
            else:
                report.violations.append(violation)
        return report
