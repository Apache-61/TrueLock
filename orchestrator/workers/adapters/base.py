"""The adapter interface and the structured result every AI must return.

`orchestrator/README.md` fixes the handoff shape. This module makes it a
parsed, validated object rather than free text, because the worker has
to *act* on it: open a PR or not, mark BLOCKED or not, escalate to a
human or not. A narrative answer cannot drive those branches safely.

Key defensive choice: an unparseable or missing result is an **error**,
never an implicit success. A model that fails to answer in the contract
gets its task recorded as FAILED with the raw output attached.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Protocol

#: Statuses the AI may report, mapped onto what the worker then does.
VALID_STATUSES = ("DONE", "PARTIAL", "BLOCKED", "FAILED", "PROPOSAL")


class AdapterError(RuntimeError):
    """The AI backend could not be invoked or did not answer in contract."""


@dataclass
class SuiteResult:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "details": self.details,
        }


@dataclass
class AIResult:
    """The structured output contract for a development AI call."""

    task_id: str
    status: str = "FAILED"
    summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    tests: SuiteResult = field(default_factory=SuiteResult)
    new_dependencies: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)
    documentation_changes: list[str] = field(default_factory=list)
    next_recommended_tasks: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    raw_output: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status in ("DONE", "PARTIAL")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tests"] = self.tests.to_dict()
        data.pop("raw_output", None)
        # `recommended_next_tasks` is the spelling used in some task
        # briefs; `next_recommended_tasks` is the one in
        # orchestrator/README.md. Emit the canonical key and keep the
        # alias so neither reader breaks.
        data["recommended_next_tasks"] = list(self.next_recommended_tasks)
        return data


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _as_tests(value: Any) -> SuiteResult:
    if isinstance(value, dict):
        return SuiteResult(
            passed=int(value.get("passed", 0) or 0),
            failed=int(value.get("failed", 0) or 0),
            skipped=int(value.get("skipped", 0) or 0),
            details=str(value.get("details", "") or ""),
        )
    return SuiteResult(details=str(value) if value else "")


def result_from_dict(data: dict[str, Any], *, task_id: str = "", raw: str = "") -> AIResult:
    status = str(data.get("status", "")).strip().upper()
    if status not in VALID_STATUSES:
        status = "DONE" if status in ("SUCCESS", "OK", "COMPLETE", "COMPLETED") else "FAILED"
    return AIResult(
        task_id=str(data.get("task_id") or task_id),
        status=status,
        summary=str(data.get("summary", "")).strip(),
        changed_files=_as_list(data.get("changed_files")),
        tests=_as_tests(data.get("tests")),
        new_dependencies=_as_list(data.get("new_dependencies")),
        known_issues=_as_list(data.get("known_issues")),
        documentation_changes=_as_list(data.get("documentation_changes")),
        next_recommended_tasks=_as_list(
            data.get("next_recommended_tasks") or data.get("recommended_next_tasks")
        ),
        requires_human_review=bool(data.get("requires_human_review", False)),
        raw_output=raw,
    )


_FENCE = re.compile(r"```(?:json)?\s*\n(?P<body>\{.*?\})\s*\n```", re.DOTALL)


def extract_result(text: str, *, task_id: str = "") -> AIResult:
    """Pull the result object out of an AI's output.

    Tries, in order: the whole output as JSON, the last fenced JSON
    block, then the last balanced top-level `{...}` span. The *last*
    match wins because a model that corrects itself puts the final
    answer last.
    """
    if not text or not text.strip():
        raise AdapterError("the AI returned no output at all")

    stripped = text.strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return result_from_dict(data, task_id=task_id, raw=text)
    except json.JSONDecodeError:
        pass

    candidates = [match.group("body") for match in _FENCE.finditer(stripped)]
    candidates.extend(_balanced_spans(stripped))
    for candidate in reversed(candidates):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and ("status" in data or "task_id" in data):
            return result_from_dict(data, task_id=task_id, raw=text)

    raise AdapterError(
        "the AI did not return a parseable result object. Expected a JSON "
        "object with task_id/status/summary. Raw output starts: "
        f"{stripped[:400]!r}"
    )


def _balanced_spans(text: str) -> list[str]:
    """Every balanced top-level `{...}` span, ignoring braces in strings."""
    spans: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    spans.append(text[start : index + 1])
    return spans


class AIAdapter(Protocol):
    """What every execution backend must provide."""

    name: str

    def execute(self, prompt: str, *, task_id: str, workdir: str, timeout: int) -> AIResult:
        """Run the task and return the structured result."""
        ...
