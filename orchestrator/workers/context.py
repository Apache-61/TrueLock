"""Build the bounded context pack handed to the AI.

The rule from `orchestrator/README.md` and `research/ai/README.md`
("High-value cost controls"): **never send the whole project history**.
The next worker reads a structured handoff plus the repository state, not
a conversation transcript.

So the pack carries exactly seven things, and each has a budget:

1. the task (objective, acceptance criteria, tests required);
2. the path budget (allowed / forbidden);
3. the contracts the task actually touches -- selected by matching the
   task's paths and prose against `docs/contracts/`, not by shipping all
   eight;
4. project state, trimmed to "Implemented" and "Blocked";
5. the handoffs of the tasks this one depends on;
6. the authorization rules the worker must not cross (CONTRIBUTING 5);
7. the output schema the AI must return.

Everything included is recorded in `included`, and everything dropped
for budget in `omitted`, so a run can always answer "what did the model
actually see?" -- which is the same auditability standard
`ARCHITECTURE.md` 1 demands of the forensic side.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scope import repo_relative
from .tasks import TaskSpec

#: Per-document and total character budgets. Deliberately generous
#: enough for real contracts, small enough that a task cannot quietly
#: turn into a whole-repository prompt.
DEFAULT_DOC_BUDGET = 6_000
DEFAULT_TOTAL_BUDGET = 60_000

#: Documents every task needs regardless of subject.
ALWAYS_INCLUDE = ("CONTRIBUTING.md", "docs/testing.md")

#: Which contract docs are relevant to which path prefixes.
CONTRACT_HINTS = {
    "domain/": ("docs/contracts/domain.md",),
    "detection/": ("docs/contracts/detector.md", "docs/contracts/leads.md"),
    "agent/": ("docs/contracts/agent-tools.md", "docs/contracts/investigation.md"),
    "evidence/": ("docs/contracts/evidence.md", "docs/contracts/case.md"),
    "backend/": ("docs/contracts/api.md",),
    "frontend/": ("docs/contracts/api.md",),
    "orchestrator/": (),
    "scripts/": (),
}


def _trim(text: str, budget: int) -> tuple[str, bool]:
    if len(text) <= budget:
        return text, False
    cut = text[:budget].rsplit("\n", 1)[0]
    return cut + f"\n\n[... trimmed to {budget} characters by the context budget ...]", True


def _extract_sections(text: str, headings: tuple[str, ...]) -> str:
    """Keep only the named `##` sections of a Markdown document."""
    kept: list[str] = []
    for heading in headings:
        match = re.search(
            rf"^#{{1,6}}\s*{re.escape(heading)}\s*$(?P<rest>.*?)(?=^#{{1,6}}\s|\Z)",
            text,
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        if match:
            kept.append(f"## {heading}\n{match.group('rest').rstrip()}")
    return "\n\n".join(kept)


@dataclass
class ContextPack:
    """What the AI is allowed to see for one task."""

    task: TaskSpec
    documents: dict[str, str] = field(default_factory=dict)
    dependency_handoffs: dict[str, str] = field(default_factory=dict)
    included: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(len(value) for value in self.documents.values()) + sum(
            len(value) for value in self.dependency_handoffs.values()
        )

    def render(self) -> str:
        """The prompt body. Ordered so constraints precede the work."""
        task = self.task
        parts: list[str] = []

        parts.append(
            "# Task context pack\n\n"
            "This is the complete context for one task. It is deliberately "
            "bounded: you are not given the project's conversation history, "
            "and you should not ask for it. If something you need is genuinely "
            "missing, stop and report it as a blocker rather than guessing."
        )

        parts.append(
            f"## Task {task.task_id}: {task.title}\n\n"
            f"- type: {task.task_type}\n"
            f"- priority: {task.priority}\n"
            f"- issue: {task.html_url or '#' + str(task.issue_number)}\n"
            f"- execution mode: {task.execution_mode}\n"
            f"- depends on: {', '.join(task.depends_on) or 'none'}\n"
        )

        if task.objective:
            parts.append(f"## Objective\n\n{task.objective}")

        if task.acceptance_criteria:
            criteria = "\n".join(f"- [ ] {item}" for item in task.acceptance_criteria)
            parts.append(f"## Acceptance criteria\n\n{criteria}")

        if task.tests_required:
            parts.append(f"## Tests required\n\n{task.tests_required}")

        if task.documentation_requirements:
            parts.append(
                f"## Documentation requirements\n\n{task.documentation_requirements}"
            )

        allowed = "\n".join(f"- {path}" for path in task.allowed_paths) or "- (none declared)"
        forbidden = "\n".join(f"- {path}" for path in task.forbidden_paths) or "- (none declared)"
        parts.append(
            "## Path budget -- hard constraint\n\n"
            "You may create or modify files **only** under these paths:\n\n"
            f"{allowed}\n\n"
            "You must not touch these under any circumstance:\n\n"
            f"{forbidden}\n\n"
            "If completing this task would require changing a path outside the "
            "allowed list, **stop**. Do not widen the scope. Return "
            'status "BLOCKED" and name the missing dependency in known_issues. '
            "A correct blocker is worth more than an out-of-scope diff."
        )

        if self.dependency_handoffs:
            joined = "\n\n".join(
                f"### {task_id}\n\n{body}" for task_id, body in self.dependency_handoffs.items()
            )
            parts.append(f"## Handoffs from dependencies\n\n{joined}")

        if self.documents:
            joined = "\n\n".join(
                f"### `{name}`\n\n{body}" for name, body in self.documents.items()
            )
            parts.append(f"## Reference documents\n\n{joined}")

        return "\n\n".join(parts)


def select_documents(task: TaskSpec, repo_root: Path) -> list[str]:
    """Choose the few documents this task actually needs.

    Selection is by the task's own paths and prose -- a detector task
    gets the detector contract, not the API contract -- plus any file the
    task text names explicitly.
    """
    wanted: list[str] = list(ALWAYS_INCLUDE)

    for path in task.allowed_paths:
        for prefix, contracts in CONTRACT_HINTS.items():
            if path.startswith(prefix):
                wanted.extend(contracts)

    # Anything the task names explicitly, e.g. `docs/contracts/agent-tools.md`.
    haystack = " ".join(
        [task.body, task.objective, task.tests_required, task.documentation_requirements]
    )
    for reference in re.findall(r"`([\w./-]+\.(?:md|json|ya?ml|py|sql))`", haystack):
        candidate = repo_relative(reference)
        if (repo_root / candidate).is_file():
            wanted.append(candidate)

    # Module READMEs for the directories the task owns.
    for path in task.allowed_paths:
        directory = path.split("*")[0].rstrip("/")
        readme = f"{directory}/README.md" if directory else ""
        if readme and (repo_root / readme).is_file():
            wanted.append(readme)

    ordered: list[str] = []
    for name in wanted:
        if name not in ordered and (repo_root / name).is_file():
            ordered.append(name)
    return ordered


def build_context(
    task: TaskSpec,
    repo_root: Path,
    *,
    doc_budget: int = DEFAULT_DOC_BUDGET,
    total_budget: int = DEFAULT_TOTAL_BUDGET,
    dependency_handoffs: dict[str, str] | None = None,
) -> ContextPack:
    """Assemble the pack, respecting both per-document and total budgets."""
    pack = ContextPack(task=task, dependency_handoffs=dict(dependency_handoffs or {}))

    state_file = repo_root / "PROJECT_STATE.md"
    if state_file.is_file():
        trimmed = _extract_sections(
            state_file.read_text(encoding="utf-8"),
            ("Implemented", "In progress", "Blocked", "Open decisions"),
        )
        body, was_trimmed = _trim(trimmed, doc_budget)
        pack.documents["PROJECT_STATE.md (excerpt)"] = body
        pack.included.append("PROJECT_STATE.md (excerpt)")
        if was_trimmed:
            pack.omitted.append("PROJECT_STATE.md (partially trimmed)")

    for name in select_documents(task, repo_root):
        if pack.size >= total_budget:
            pack.omitted.append(f"{name} (total context budget reached)")
            continue
        text = (repo_root / name).read_text(encoding="utf-8")
        body, was_trimmed = _trim(text, doc_budget)
        pack.documents[name] = body
        pack.included.append(name)
        if was_trimmed:
            pack.omitted.append(f"{name} (trimmed to {doc_budget} chars)")

    return pack
