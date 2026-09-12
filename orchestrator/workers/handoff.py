"""The handoff: `task-result.json` plus the durable history entry.

Two artifacts, one source of truth:

* `task-result.json` -- the machine-readable handoff from
  `orchestrator/README.md`, attached to the PR and written to
  `.state/` for the local run;
* `history/ai-activity/<date>-<TASK-ID>-<run-id>.md` -- the durable
  record required by CONTRIBUTING.md 6 and
  `history/ai-activity/README.md`.

The file name follows the convention already in the repository
(`YYYY-MM-DD-task-###-slug.md`) with the AI run ID as the slug, so a run
is addressable by its ID *and* sorts by date next to its siblings.

Escalation rules implemented here, per the operating rules:

* a change that touches architecture, contracts, or schemas demands an
  ADR -- the worker cannot write one on its own authority, so it raises
  the requirement and forces human review;
* an experiment demands an entry under `history/experiments/`.

Only what the AI *actually* reported is written. If the AI returned no
summary, the handoff says so rather than inventing a plausible one.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .scope import repo_relative
from .adapters.base import AIResult

#: Touching any of these means the change is architectural (ADR required).
ADR_TRIGGER_PATHS = (
    "ARCHITECTURE.md",
    "docs/contracts/",
    "domain/schemas/",
    "database/migrations/",
    "DECISIONS.md",
)


def new_run_id() -> str:
    """Short, sortable, unique enough for one hackathon's worth of runs."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"AI-RUN-{stamp}-{uuid.uuid4().hex[:6]}"


def requires_adr(changed_paths: list[str]) -> list[str]:
    """Which architectural triggers these paths hit."""
    hits: list[str] = []
    for path in changed_paths:
        normalized = repo_relative(path)
        for trigger in ADR_TRIGGER_PATHS:
            if (normalized == trigger or normalized.startswith(trigger)) and trigger not in hits:
                hits.append(trigger)
    return hits


@dataclass
class Handoff:
    """Everything one task execution produced."""

    run_id: str
    worker_id: str
    task_id: str
    issue_number: int
    branch: str
    started_at: str
    finished_at: str = ""
    goal: str = ""
    result: AIResult | None = None
    validation_summary: str = ""
    validation_detail: str = ""
    outcome: str = "UNKNOWN"
    pr_url: str = ""
    adr_required: list[str] = field(default_factory=list)
    experiment_required: bool = False
    scope_violations: list[str] = field(default_factory=list)
    context_included: list[str] = field(default_factory=list)
    context_omitted: list[str] = field(default_factory=list)
    routing_events: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # -- machine-readable -------------------------------------------
    def to_dict(self) -> dict:
        result = self.result
        payload = {
            "task_id": self.task_id,
            "status": self.outcome,
            "summary": (result.summary if result and result.summary else
                        "No summary was returned by the AI worker."),
            "changed_files": list(result.changed_files) if result else [],
            "tests": result.tests.to_dict() if result else {"passed": 0, "failed": 0, "skipped": 0, "details": ""},
            "new_dependencies": list(result.new_dependencies) if result else [],
            "known_issues": list(result.known_issues) if result else [],
            "documentation_changes": list(result.documentation_changes) if result else [],
            "next_recommended_tasks": list(result.next_recommended_tasks) if result else [],
            "requires_human_review": bool(result.requires_human_review) if result else True,
        }
        # Alias kept for readers using the other spelling of this field.
        payload["recommended_next_tasks"] = list(payload["next_recommended_tasks"])
        payload["run"] = {
            "run_id": self.run_id,
            "worker_id": self.worker_id,
            "issue": self.issue_number,
            "branch": self.branch,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "validation": self.validation_summary,
            "pull_request": self.pr_url,
            "adr_required": list(self.adr_required),
            "experiment_record_required": self.experiment_required,
            "scope_violations": list(self.scope_violations),
            "routing_events": list(self.routing_events),
            "context_included": list(self.context_included),
            "context_omitted": list(self.context_omitted),
        }
        if self.adr_required or self.experiment_required:
            payload["requires_human_review"] = True
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    # -- human-readable ---------------------------------------------
    def history_filename(self) -> str:
        date = (self.started_at or datetime.now(timezone.utc).isoformat())[:10]
        return f"{date}-{self.task_id.lower()}-{self.run_id.lower()}.md"

    def render_markdown(self) -> str:
        result = self.result
        lines = [
            f"# {self.run_id}  {self.task_id}",
            "",
            f"- **worker:** {self.worker_id}",
            f"- **task:** {self.task_id} (issue #{self.issue_number})",
            f"- **branch:** `{self.branch}`",
            f"- **start:** {self.started_at}",
            f"- **end:** {self.finished_at or 'n/a'}",
            f"- **result:** {self.outcome}",
            f"- **pull request:** {self.pr_url or 'none'}",
            "",
            "## Goal",
            "",
            self.goal or "_not recorded_",
            "",
            "## Changes",
            "",
        ]
        changed = list(result.changed_files) if result else []
        lines.extend([f"- `{path}`" for path in changed] or ["_No files were changed._"])

        lines += ["", "## Summary", "", (result.summary if result and result.summary
                                         else "_The AI worker returned no summary._")]

        lines += ["", "## Tests", "", "```", self.validation_summary or "not run", "```"]
        if self.validation_detail:
            lines += ["", "<details><summary>Validation detail</summary>", "",
                      "```", self.validation_detail.strip()[-6000:], "```", "", "</details>"]

        lines += ["", "## Known issues", ""]
        known = list(result.known_issues) if result else []
        if self.scope_violations:
            known = known + [f"Scope violation: {item}" for item in self.scope_violations]
        lines.extend([f"- {item}" for item in known] or ["- None reported."])

        lines += ["", "## Next recommended tasks", ""]
        next_tasks = list(result.next_recommended_tasks) if result else []
        lines.extend([f"- {item}" for item in next_tasks] or ["- None recommended."])

        if self.adr_required:
            lines += [
                "",
                "## ADR REQUIRED",
                "",
                "This run touched architectural surface, so a decision record is "
                "required before it can be merged (`history/decisions/README.md`, "
                "CONTRIBUTING.md 5). Triggered by:",
                "",
                *[f"- `{trigger}`" for trigger in self.adr_required],
                "",
                "The worker does not write ADRs: recording a decision is a human "
                "act, and an AI-authored record of a decision nobody made is worse "
                "than no record.",
            ]

        if self.experiment_required:
            lines += [
                "",
                "## EXPERIMENT RECORD REQUIRED",
                "",
                "This task is an experiment, so it needs an entry under "
                "`history/experiments/` capturing the hypothesis, what was tried, "
                "and what the outcome actually was -- including if it failed.",
            ]

        if self.context_included or self.context_omitted:
            lines += ["", "## Context given to the AI", ""]
            lines += [f"- included: `{item}`" for item in self.context_included]
            lines += [f"- omitted: {item}" for item in self.context_omitted]

        if self.routing_events:
            lines += ["", "## Routing", "", "```", *self.routing_events, "```"]

        if self.notes:
            lines += ["", "## Worker notes", "", *[f"- {note}" for note in self.notes]]

        lines += [
            "",
            "---",
            "",
            "Handoff (`orchestrator/README.md` -> AI-to-AI handoff format):",
            "",
            "```json",
            self.to_json().rstrip(),
            "```",
        ]
        return "\n".join(lines) + "\n"

    # -- writing ------------------------------------------------------
    def write(
        self, repo_root: Path, *, dry_run: bool = False, state_only: bool = False
    ) -> dict[str, Path]:
        """Write the handoff artifacts. Returns the paths written.

        `state_only` writes just the `.state/` record and skips the
        `history/ai-activity/` entry. Failure paths use it, and the
        reason is not tidiness -- it is that a failed run must leave the
        repository exactly as it found it.

        `history/ai-activity/` is tracked, so writing there leaves an
        untracked file behind. The next run then refuses to start with
        "working tree is dirty", fails, and writes *another* one. One
        transient failure -- a flaky network, an encoding problem, a
        cancelled run -- permanently wedges the machine, and in
        `--continuous` it trips the three-failure circuit breaker with
        two failures the worker caused itself.

        `.state/` is gitignored *and* excluded by `Git.is_clean()`
        (`SCRATCH_NAMES`), so the record survives for debugging without
        blocking anything. The issue comment carries the summary either
        way.
        """
        history_path = repo_root / "history" / "ai-activity" / self.history_filename()
        state_path = repo_root / ".state" / f"task-result-{self.run_id}.json"
        written: dict[str, Path] = {"task_result": state_path}
        if not dry_run:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(self.to_json(), encoding="utf-8")
            if not state_only:
                history_path.parent.mkdir(parents=True, exist_ok=True)
                history_path.write_text(self.render_markdown(), encoding="utf-8")
        if not state_only:
            written["history"] = history_path
        return written


def append_timeline(repo_root: Path, *, handoff: Handoff, dry_run: bool = False) -> None:
    """One line in `history/timeline.md`, per CONTRIBUTING.md 6."""
    timeline = repo_root / "history" / "timeline.md"
    if dry_run or not timeline.is_file():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = "no summary"
    if handoff.result and handoff.result.summary:
        summary = re.sub(r"\s+", " ", handoff.result.summary).strip()
        if len(summary) > 160:
            summary = summary[:157].rstrip() + "..."
    line = (
        f"{stamp} | {handoff.task_id} | {handoff.worker_id} ({handoff.run_id}) | "
        f"{handoff.outcome}: {summary} See "
        f"`history/ai-activity/{handoff.history_filename()}`.\n"
    )
    with timeline.open("a", encoding="utf-8") as handle:
        handle.write("\n" + line.rstrip() + "\n")
