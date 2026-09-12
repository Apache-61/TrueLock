"""Parse a GitHub issue into a `TaskSpec`.

GitHub Issues are the source of truth for task state (ADR-0003), and the
Markdown files under `tasks/` are the human-readable mirror. This module
reads the issue, because "if the mirror and the GitHub issue ever
disagree, the GitHub issue wins" (`tasks/README.md`).

Two body dialects exist in this repository and both are supported:

* the mirror/template dialect used by `tasks/templates/task-template.md`
  and `.github/ISSUE_TEMPLATE/*` -- ``- **type:** feature``
* the seeded-issue dialect used by TASK-001..007 --
  ``**Priority:** P0`` / ``**Depends on:** none``

Labels, when they exist, override the body: a label is a deliberate act
by a human or the worker, whereas the body is prose that can go stale.
At the time of writing the repository's labels have not been created yet
(`PROJECT_STATE.md` -> "Blocked"), which is exactly why the body parse
has to work on its own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TASK_ID_PATTERN = re.compile(r"\bTASK-(\d{1,4})\b")
PRIORITY_PATTERN = re.compile(r"\bP([0-3])\b")

#: Task types recognised by `tasks/templates/task-template.md`.
KNOWN_TYPES = {
    "feature",
    "bug",
    "research",
    "experiment",
    "integration",
    "documentation",
    "docs",
    "security",
    "decision",
}

#: type -> branch prefix, per CONTRIBUTING.md 3, which names exactly
#: four prefixes. Types without a prefix of their own ride `feature/`.
BRANCH_PREFIX_BY_TYPE = {
    "research": "research",
    "experiment": "experiment",
    "bug": "fix",
}
DEFAULT_BRANCH_PREFIX = "feature"

_STOPWORDS = {"a", "an", "and", "the", "of", "for", "to", "with", "on", "in"}


def slugify(text: str, *, max_words: int = 5) -> str:
    """Turn a task title into the branch-name slug used by CONTRIBUTING 3."""
    text = TASK_ID_PATTERN.sub(" ", text)
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    kept = [word for word in words if word not in _STOPWORDS] or words
    return "-".join(kept[:max_words]) or "task"


def _field(body: str, *names: str) -> str:
    """Read a ``**name:** value`` field, with or without a leading dash.

    Values may wrap onto indented continuation lines -- the seeded task
    files wrap at 72 columns -- so a `depends_on` naming a task on its
    second line is still seen. A blank line, a new field, or a heading
    ends the value.
    """
    for name in names:
        pattern = re.compile(
            rf"^[ \t]*(?:[-*][ \t]*)?\*\*{re.escape(name)}:?\*\*:?[ \t]*(?P<value>.*)$",
            re.IGNORECASE | re.MULTILINE,
        )
        match = pattern.search(body)
        if not match:
            continue
        parts = [match.group("value").strip()]
        for line in body[match.end() :].splitlines()[1:]:
            stripped = line.strip()
            if not stripped or not line[:1].isspace():
                break
            if stripped.startswith(("**", "#", "-", "*", "|", "```")):
                break
            parts.append(stripped)
        return " ".join(part for part in parts if part).strip()
    return ""


def _fenced_block(body: str, heading: str) -> list[str]:
    """Read the fenced code block that follows a ``## heading``."""
    pattern = re.compile(
        rf"^#{{1,6}}\s*{re.escape(heading)}\s*$(?P<rest>.*?)(?=^#{{1,6}}\s|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return []
    section = match.group("rest")
    fence = re.search(r"```[a-zA-Z]*\n(?P<inner>.*?)```", section, re.DOTALL)
    lines = (fence.group("inner") if fence else section).splitlines()
    return _clean_path_lines(lines)


def _bulleted_block(body: str, *headings: str) -> list[str]:
    """Read a ``**Heading:**`` paragraph followed by ``- `path``` bullets."""
    for heading in headings:
        pattern = re.compile(
            rf"\*\*{re.escape(heading)}:?\*\*:?\s*\n(?P<rest>(?:[ \t]*[-*].*\n?)+)",
            re.IGNORECASE,
        )
        match = pattern.search(body)
        if match:
            return _clean_path_lines(match.group("rest").splitlines())
    return []


def _clean_path_lines(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        item = line.strip().lstrip("-*").strip()
        # Drop trailing annotations such as "(frozen)" *before* unquoting,
        # otherwise the closing backtick survives and the resulting glob
        # silently matches nothing -- a scope check that never fires.
        item = re.sub(r"\s*\((?:[^()]*)\)\s*$", "", item).strip()
        item = item.strip("`").strip()
        item = re.sub(r"\s*\((?:[^()]*)\)\s*$", "", item).strip()
        if item and not item.startswith("#"):
            cleaned.append(item)
    return cleaned


def _paths(body: str, fenced_heading: str, *bullet_headings: str) -> list[str]:
    return _fenced_block(body, fenced_heading) or _bulleted_block(body, *bullet_headings)


def _acceptance_criteria(body: str) -> list[str]:
    pattern = re.compile(
        r"^#{1,6}\s*Acceptance criteria\s*$(?P<rest>.*?)(?=^#{1,6}\s|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        match = re.search(
            r"\*\*Acceptance criteria:?\*\*:?\s*\n(?P<rest>(?:[ \t]*[-*].*\n?)+)",
            body,
            re.IGNORECASE,
        )
    if not match:
        return []
    criteria: list[str] = []
    for line in match.group("rest").splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            item = re.sub(r"^\[[ xX]?\]\s*", "", stripped.lstrip("-* ").strip())
            if item:
                criteria.append(item)
        elif stripped and criteria and line[:1].isspace():
            # Continuation of the previous wrapped bullet.
            criteria[-1] = f"{criteria[-1]} {stripped}"
    return criteria


def _section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^#{{1,6}}\s*{re.escape(heading)}\s*$(?P<rest>.*?)(?=^#{{1,6}}\s|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if match:
        return match.group("rest").strip()
    inline = re.search(
        rf"\*\*{re.escape(heading)}:?\*\*:?\s*\n(?P<rest>.*?)(?=\n\*\*|\Z)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    return inline.group("rest").strip() if inline else ""


def _is_yes(value: str) -> bool:
    return value.strip().lower().startswith(("yes", "y ", "true", "si", "sí"))


def _is_no(value: str) -> bool:
    return value.strip().lower().startswith(("no", "none", "false"))


@dataclass(frozen=True)
class TaskSpec:
    """One unit of authorized work, as the worker understands it."""

    task_id: str
    issue_number: int
    title: str
    body: str
    task_type: str = "feature"
    priority: str = "P2"
    status: str = "READY"
    execution_mode: str = "auto"
    depends_on: tuple[str, ...] = ()
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    objective: str = ""
    tests_required: str = ""
    documentation_requirements: str = ""
    human_authorization: bool = False
    labels: tuple[str, ...] = ()
    issue_state: str = "open"
    html_url: str = ""

    @property
    def priority_rank(self) -> int:
        """P0 sorts first. Anything unparseable sorts last, not first."""
        match = PRIORITY_PATTERN.search(self.priority)
        return int(match.group(1)) if match else 9

    @property
    def branch_prefix(self) -> str:
        return BRANCH_PREFIX_BY_TYPE.get(self.task_type, DEFAULT_BRANCH_PREFIX)

    @property
    def branch_name(self) -> str:
        return f"{self.branch_prefix}/{self.task_id}-{slugify(self.title)}"

    @property
    def requires_human_execution(self) -> bool:
        """True when the worker must propose rather than implement."""
        return self.execution_mode == "human" or self.human_authorization

    def sort_key(self) -> tuple[int, int]:
        return (self.priority_rank, self.issue_number)


def parse_issue(issue: dict) -> TaskSpec:
    """Build a `TaskSpec` from a GitHub issue payload."""
    body = issue.get("body") or ""
    title = issue.get("title") or ""
    labels = tuple(
        label["name"] if isinstance(label, dict) else str(label)
        for label in issue.get("labels", [])
    )
    label_set = set(labels)

    match = TASK_ID_PATTERN.search(title) or TASK_ID_PATTERN.search(body)
    task_id = f"TASK-{int(match.group(1)):03d}" if match else f"ISSUE-{issue.get('number', 0)}"

    task_type = _field(body, "type").split("|")[0].strip().lower()
    for label in labels:
        if label.startswith("type:"):
            task_type = label.split(":", 1)[1]
            break
    if task_type not in KNOWN_TYPES:
        task_type = "feature"
    if task_type == "docs":
        task_type = "documentation"

    priority = _field(body, "priority").strip()
    for label in labels:
        if label.startswith("priority:"):
            priority = label.split(":", 1)[1]
            break
    priority_match = PRIORITY_PATTERN.search(priority)
    priority = priority_match.group(0) if priority_match else "P2"

    status = _field(body, "status").split("|")[0].strip().upper()
    status_labels = {
        "status:ready": "READY",
        "status:claimed": "CLAIMED",
        "status:active": "IN_PROGRESS",
        "status:review": "READY_FOR_REVIEW",
        "status:blocked": "BLOCKED",
        "status:done": "MERGED",
        "status:research": "RESEARCH",
    }
    for label in labels:
        if label in status_labels:
            status = status_labels[label]
            break
    if not status:
        status = "READY"

    human_auth_raw = _field(body, "human_authorization", "Human authorization required",
                            "human authorization")
    human_authorization = _is_yes(human_auth_raw)

    execution_mode = _field(body, "execution_mode").split("|")[0].strip().lower()
    if "execution:human" in label_set:
        execution_mode = "human"
    elif "execution:auto" in label_set:
        execution_mode = "auto"
    if execution_mode not in ("auto", "human"):
        execution_mode = "human" if human_authorization else "auto"

    depends_raw = _field(body, "depends_on", "Depends on", "dependencies")
    depends_on: tuple[str, ...] = ()
    if depends_raw and not _is_no(depends_raw):
        depends_on = tuple(
            f"TASK-{int(number):03d}" for number in TASK_ID_PATTERN.findall(depends_raw)
        )

    return TaskSpec(
        task_id=task_id,
        issue_number=int(issue.get("number", 0)),
        title=title,
        body=body,
        task_type=task_type,
        priority=priority,
        status=status,
        execution_mode=execution_mode,
        depends_on=depends_on,
        allowed_paths=tuple(_paths(body, "Allowed paths", "Allowed paths")),
        forbidden_paths=tuple(_paths(body, "Forbidden paths", "Forbidden paths")),
        acceptance_criteria=tuple(_acceptance_criteria(body)),
        objective=_section(body, "Objective"),
        tests_required=_section(body, "Tests required"),
        documentation_requirements=_section(body, "Documentation requirements"),
        human_authorization=human_authorization,
        labels=labels,
        issue_state=issue.get("state", "open").lower(),
        html_url=issue.get("html_url", ""),
    )


@dataclass
class TaskQueue:
    """The READY tasks visible to this worker, in the order to try them."""

    tasks: list[TaskSpec] = field(default_factory=list)

    def ordered(self) -> list[TaskSpec]:
        """Priority first (P0 -> P3), then issue number for stability.

        Stable ordering matters beyond tidiness: four workers reading the
        same queue try tasks in the same order, so races concentrate on
        one task and are resolved by the claim protocol, instead of being
        smeared across the whole queue.
        """
        return sorted(self.tasks, key=lambda task: task.sort_key())
