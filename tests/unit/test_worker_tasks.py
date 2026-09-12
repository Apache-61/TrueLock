"""Parsing GitHub issues into TaskSpecs (orchestrator/workers/tasks.py).

The worker's every downstream decision -- priority order, dependency
gating, scope enforcement, branch naming -- rests on this parse being
right, so these tests use the *real* dialects found in this repository:
the seeded issue bodies for TASK-001..007 and the mirror files under
`tasks/ready/`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.workers.tasks import TaskQueue, parse_issue, slugify

REPO_ROOT = Path(__file__).resolve().parents[2]

SEEDED_ISSUE_BODY = """**Priority:** P0
**Owner area:** backend/data (Agent B)
**Depends on:** none
**Human authorization required:** No

**Objective:**
Implement `domain/entities/` and `scripts/ingest/` normalizers.

**Allowed paths:**
- `domain/entities/**`
- `backend/repositories/**`
- `scripts/ingest/**`

**Forbidden paths:**
- `domain/schemas/**` (frozen)
- `frontend/**`

**Acceptance criteria:**
- [ ] Every schema has a corresponding entity class
- [ ] Malformed records are rejected, not guessed at
"""


def issue(number=1, title="TASK-001: Canonical ingestion", body=SEEDED_ISSUE_BODY, labels=None,
          state="open"):
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": [{"name": name} for name in (labels or [])],
        "html_url": f"https://github.com/x/y/issues/{number}",
    }


class TestSeededIssueDialect:
    def test_core_fields(self):
        spec = parse_issue(issue())
        assert spec.task_id == "TASK-001"
        assert spec.priority == "P0"
        assert spec.status == "READY"
        assert spec.execution_mode == "auto"
        assert spec.human_authorization is False
        assert spec.depends_on == ()

    def test_allowed_and_forbidden_paths_are_unquoted(self):
        spec = parse_issue(issue())
        assert spec.allowed_paths == (
            "domain/entities/**",
            "backend/repositories/**",
            "scripts/ingest/**",
        )
        # The "(frozen)" annotation must not leave a stray backtick: a
        # malformed glob would silently match nothing and disable the guard.
        assert spec.forbidden_paths == ("domain/schemas/**", "frontend/**")

    def test_acceptance_criteria_lose_their_checkboxes(self):
        spec = parse_issue(issue())
        assert spec.acceptance_criteria == (
            "Every schema has a corresponding entity class",
            "Malformed records are rejected, not guessed at",
        )


class TestTemplateDialect:
    BODY = """- **type:** research
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **depends_on:** TASK-001 (entities) and
  TASK-003
- **human_authorization:** no

## Objective

Spike the thing.

## Allowed paths

```
research/graph/**
```

## Forbidden paths

```
domain/**
```

## Acceptance criteria

- [ ] A written conclusion exists, including if the answer is "no"
"""

    def test_fields_and_fenced_paths(self):
        spec = parse_issue(issue(number=9, title="TASK-009: Graph spike", body=self.BODY))
        assert spec.task_type == "research"
        assert spec.priority == "P1"
        assert spec.allowed_paths == ("research/graph/**",)
        assert spec.forbidden_paths == ("domain/**",)

    def test_dependencies_wrapped_across_lines_are_all_found(self):
        """The seeded task files wrap at 72 columns; a dependency on the
        second line must not be silently dropped -- that would let the
        worker build on unmerged work."""
        spec = parse_issue(issue(number=9, body=self.BODY))
        assert spec.depends_on == ("TASK-001", "TASK-003")

    def test_research_task_gets_a_research_branch(self):
        spec = parse_issue(issue(number=9, title="TASK-009: Graph spike", body=self.BODY))
        assert spec.branch_name == "research/TASK-009-graph-spike"


class TestLabelsOverrideBody:
    """Labels are a deliberate act; body prose goes stale."""

    def test_priority_type_status_and_execution_mode(self):
        spec = parse_issue(
            issue(
                body="- **priority:** P3\n- **type:** feature\n- **execution_mode:** auto\n",
                labels=["priority:P0", "type:research", "status:blocked", "execution:human"],
            )
        )
        assert spec.priority == "P0"
        assert spec.task_type == "research"
        assert spec.status == "BLOCKED"
        assert spec.execution_mode == "human"
        assert spec.requires_human_execution is True


class TestHumanAuthorization:
    @pytest.mark.parametrize("value,expected", [("Yes", True), ("yes — adds APIs", True),
                                                ("No", False), ("no", False)])
    def test_human_authorization_field(self, value, expected):
        spec = parse_issue(issue(body=f"**Human authorization required:** {value}\n"))
        assert spec.human_authorization is expected

    def test_human_authorization_implies_human_execution(self):
        spec = parse_issue(issue(body="**Human authorization required:** Yes\n"))
        assert spec.execution_mode == "human"
        assert spec.requires_human_execution is True


class TestBranchNaming:
    @pytest.mark.parametrize(
        "task_type,prefix",
        [("feature", "feature"), ("integration", "feature"), ("documentation", "feature"),
         ("research", "research"), ("experiment", "experiment"), ("bug", "fix")],
    )
    def test_prefix_per_type(self, task_type, prefix):
        spec = parse_issue(issue(body=f"- **type:** {task_type}\n"))
        assert spec.branch_name.startswith(f"{prefix}/TASK-001-")

    def test_slug_drops_task_id_and_stopwords(self):
        assert slugify("TASK-004: Detector framework + first 3 detectors") == (
            "detector-framework-first-3-detectors"
        )

    def test_branch_name_never_collides_with_main(self):
        spec = parse_issue(issue())
        assert spec.branch_name != "main"
        assert "/" in spec.branch_name


class TestPriorityOrdering:
    def test_p0_first_then_issue_number(self):
        queue = TaskQueue([
            parse_issue(issue(number=6, title="TASK-006: f", body="**Priority:** P1\n")),
            parse_issue(issue(number=3, title="TASK-003: c", body="**Priority:** P0\n")),
            parse_issue(issue(number=1, title="TASK-001: a", body="**Priority:** P0\n")),
            parse_issue(issue(number=9, title="TASK-009: i", body="**Priority:** P3\n")),
        ])
        assert [task.task_id for task in queue.ordered()] == [
            "TASK-001", "TASK-003", "TASK-006", "TASK-009",
        ]

    def test_unparseable_priority_sorts_last_not_first(self):
        """An unlabelled task must not jump the queue ahead of a real P0."""
        unknown = parse_issue(issue(number=2, title="TASK-002: b", body="no priority here\n"))
        p0 = parse_issue(issue(number=8, title="TASK-008: h", body="**Priority:** P0\n"))
        assert [t.task_id for t in TaskQueue([unknown, p0]).ordered()] == ["TASK-008", "TASK-002"]


class TestAgainstRealTaskFiles:
    """The seven real task files must parse without special-casing."""

    @pytest.mark.parametrize("path", sorted((REPO_ROOT / "tasks" / "ready").glob("TASK-*.md")),
                             ids=lambda p: p.name)
    def test_real_task_file_parses(self, path):
        body = path.read_text(encoding="utf-8")
        spec = parse_issue(issue(number=1, title=body.splitlines()[0].lstrip("# "), body=body))
        assert spec.task_id.startswith("TASK-")
        assert spec.priority in ("P0", "P1", "P2", "P3")
        assert spec.allowed_paths, f"{path.name} declares no allowed_paths"
        assert spec.acceptance_criteria, f"{path.name} declares no acceptance criteria"
