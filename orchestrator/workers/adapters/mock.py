"""Offline adapter for `--dry-run` and tests.

It performs the *shape* of a real execution -- returns a contract-valid
`AIResult`, optionally writes a file inside the task's allowed paths --
without calling a paid API or a local model. That is what makes the
acceptance criterion in TASK-007 ("a dry-run mode that exercises claim ->
mock-implement -> handoff without calling a real paid API") testable.

It never claims work it did not do: its summary says plainly that it is a
mock, and `requires_human_review` is True, so a mock run that somehow
reached a PR would be unmistakable in review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .base import AIResult, SuiteResult
from .claude_code import Usage


@dataclass
class MockAdapter:
    """Deterministic stand-in for a real AI backend."""

    name: str = "mock"
    status: str = "DONE"
    write_files: bool = False
    last_prompt: str = ""
    last_usage: Usage = field(default_factory=lambda: Usage(input_tokens=0, output_tokens=0))
    last_duration_s: float = 0.0
    calls: list[str] = field(default_factory=list)

    def available(self) -> bool:
        return True

    def execute(self, prompt: str, *, task_id: str, workdir: str, timeout: int = 0) -> AIResult:
        self.last_prompt = prompt
        self.calls.append(task_id)

        changed: list[str] = []
        if self.write_files:
            note = Path(workdir) / "orchestrator" / "state" / f"mock-{task_id}.txt"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(f"mock execution for {task_id}\n", encoding="utf-8")
            changed.append(str(note.relative_to(Path(workdir))))

        return AIResult(
            task_id=task_id,
            status=self.status,
            summary=(
                f"MOCK RUN for {task_id} -- no AI was called and no real "
                "implementation was produced. This output exists so the "
                "orchestration loop can be exercised end to end offline."
            ),
            changed_files=changed,
            tests=SuiteResult(details="not run by the mock adapter"),
            known_issues=["Mock adapter: the task was not actually implemented."],
            next_recommended_tasks=[],
            requires_human_review=True,
            raw_output="{\"mock\": true}",
        )
