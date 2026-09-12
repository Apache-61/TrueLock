"""The backlog definition and the guards on it.

`orchestrator/task_queue/backlog.py` is the source both the `tasks/`
mirror and the GitHub queue are rendered from, so two things have to
stay true, and neither is obvious by reading it:

1. What the seeder renders is what the worker parses. The rendered issue
   body is the *only* thing a worker sees; if the dialect drifts, the
   worker silently reads a task with no `allowed_paths` -- which means no
   scope enforcement at all.
2. The graph cannot deadlock or collide. A cycle makes every worker
   report "no eligible task" with no explanation, on all four machines
   at once; overlapping scopes between concurrently-claimable tasks
   produce merge conflicts no claim protocol can prevent.
"""
from __future__ import annotations

import pytest

from orchestrator.task_queue.backlog import (
    BACKLOG,
    BacklogError,
    TaskDefinition,
    _globs_overlap,
    by_id,
    depth,
    ready_now,
    render_graph,
    validate,
)
from orchestrator.workers.tasks import parse_issue


def make_task(task_id: str, **kwargs) -> TaskDefinition:
    defaults = dict(
        task_id=task_id,
        title=f"Task {task_id}",
        priority="P0",
        area="backend",
        objective="Do the thing.",
        allowed_paths=(f"module/{task_id}/**",),
        acceptance_criteria=("It works.",),
        tests_required="Unit tests.",
    )
    defaults.update(kwargs)
    return TaskDefinition(**defaults)


class TestTheRealBacklog:
    def test_the_shipped_backlog_is_valid(self):
        assert validate() == []

    def test_every_task_is_claimable_by_a_worker(self):
        """Each definition must survive the round trip through the queue."""
        for task in BACKLOG:
            issue = {
                "number": task.existing_issue or 900 + task.number,
                "title": f"{task.task_id}: {task.title}",
                "body": task.render_markdown(),
                "labels": [{"name": name} for name in task.labels],
                "state": "open",
            }
            spec = parse_issue(issue)
            assert spec.task_id == task.task_id
            assert spec.priority == task.priority
            assert set(spec.depends_on) == set(task.depends_on)
            # The rendered scope is the task's source paths plus where it
            # may write its tests -- every task is required to bring tests,
            # so every task must be scoped to write them.
            assert set(spec.allowed_paths) == set(task.allowed_paths) | set(
                task.test_paths
            ), task.task_id
            assert set(spec.forbidden_paths) == set(task.forbidden_paths), task.task_id
            assert len(spec.acceptance_criteria) == len(task.acceptance_criteria)
            assert spec.objective, f"{task.task_id} parsed with an empty objective"

    def test_every_task_declares_a_scope(self):
        """A task with no allowed_paths is a task with no scope enforcement."""
        for task in BACKLOG:
            assert task.allowed_paths, f"{task.task_id} declares no allowed_paths"

    def test_every_dependency_exists(self):
        index = by_id()
        for task in BACKLOG:
            for dependency in task.depends_on:
                assert dependency in index, f"{task.task_id} -> missing {dependency}"

    def test_some_work_is_claimable_immediately(self):
        """A backlog where nothing can start is a stalled team."""
        assert len(ready_now()) >= 2

    def test_every_task_may_write_its_own_tests(self):
        """Otherwise the scope guard blocks the tests the task asks for.

        Every task's "Tests required" section names files under `tests/`.
        If the rendered `allowed_paths` do not cover them, the worker
        stops the task BLOCKED for a scope violation it was instructed to
        commit -- on every task, on all four machines.
        """
        from orchestrator.workers.scope import ScopeGuard

        for task in BACKLOG:
            spec_paths = set(task.allowed_paths) | set(task.test_paths)
            guard = ScopeGuard(tuple(spec_paths), task.forbidden_paths)
            report = guard.check(["tests/unit/test_something.py"])
            assert report.ok, f"{task.task_id} cannot write its own tests"

    def test_the_graph_renders(self):
        graph = render_graph()
        assert graph.startswith("```mermaid")
        assert "TASK001" in graph


class TestValidationCatchesDeadlocks:
    def test_an_unknown_dependency_is_reported(self):
        tasks = (make_task("TASK-001", depends_on=("TASK-999",)),)
        problems = validate(tasks)
        assert any("TASK-999" in problem for problem in problems)

    def test_a_self_dependency_is_reported(self):
        tasks = (make_task("TASK-001", depends_on=("TASK-001",)),)
        assert any("itself" in problem for problem in validate(tasks))

    def test_a_cycle_is_reported(self):
        tasks = (
            make_task("TASK-001", depends_on=("TASK-002",)),
            make_task("TASK-002", depends_on=("TASK-001",)),
        )
        problems = validate(tasks)
        assert problems, "a two-task cycle must not validate"
        assert any("cycle" in problem for problem in problems)

    def test_a_longer_cycle_is_reported(self):
        tasks = (
            make_task("TASK-001", depends_on=("TASK-003",)),
            make_task("TASK-002", depends_on=("TASK-001",)),
            make_task("TASK-003", depends_on=("TASK-002",)),
        )
        assert any("cycle" in problem for problem in validate(tasks))

    def test_a_duplicate_task_id_is_reported(self):
        tasks = (make_task("TASK-001"), make_task("TASK-001"))
        assert any("duplicate" in problem for problem in validate(tasks))

    def test_depth_raises_on_a_cycle(self):
        tasks = (
            make_task("TASK-001", depends_on=("TASK-002",)),
            make_task("TASK-002", depends_on=("TASK-001",)),
        )
        with pytest.raises(BacklogError):
            depth("TASK-001", by_id(tasks))


class TestValidationCatchesCollisions:
    def test_two_concurrent_tasks_may_not_share_a_path(self):
        """Nothing orders these two, so both can be claimed at once."""
        tasks = (
            make_task("TASK-001", allowed_paths=("backend/api/**",)),
            make_task("TASK-002", allowed_paths=("backend/api/routes/leads.py",)),
        )
        problems = validate(tasks)
        assert any("concurrently" in problem for problem in problems)

    def test_a_dependency_edge_makes_a_shared_path_safe(self):
        """Ordered tasks cannot collide, so the same paths are fine."""
        tasks = (
            make_task("TASK-001", allowed_paths=("backend/api/**",)),
            make_task("TASK-002", depends_on=("TASK-001",),
                      allowed_paths=("backend/api/routes/leads.py",)),
        )
        assert validate(tasks) == []

    def test_a_transitive_dependency_also_orders_them(self):
        tasks = (
            make_task("TASK-001", allowed_paths=("frontend/**",)),
            make_task("TASK-002", depends_on=("TASK-001",), allowed_paths=("other/**",)),
            make_task("TASK-003", depends_on=("TASK-002",),
                      allowed_paths=("frontend/app/graph/**",)),
        )
        assert validate(tasks) == [], "TASK-003 transitively depends on TASK-001"

    def test_sibling_subdirectories_do_not_collide(self):
        tasks = (
            make_task("TASK-001", allowed_paths=("frontend/app/dashboard/**",)),
            make_task("TASK-002", allowed_paths=("frontend/app/graph/**",)),
        )
        assert validate(tasks) == []

    @pytest.mark.parametrize(
        "left,right,overlaps",
        [
            ("detection/**", "detection/rules/base.py", True),
            ("detection/rules/base.py", "detection/**", True),
            ("detection/rules/a.py", "detection/rules/b.py", False),
            ("frontend/app/dashboard/**", "frontend/app/graph/**", False),
            ("agent/tools/**", "agent/tools/leads.py", True),
            ("scripts/ingest/**", "scripts/validate/**", False),
            # A prefix that is not a path boundary is not an overlap:
            # "detection/graph" must not swallow "detection/graphql".
            ("detection/graph/**", "detection/graphql/**", False),
        ],
    )
    def test_glob_overlap_is_decided_on_path_boundaries(self, left, right, overlaps):
        assert _globs_overlap(left, right) is overlaps


class TestRendering:
    def test_depends_on_none_renders_readably(self):
        body = make_task("TASK-001").render_markdown()
        assert "**depends_on:** none" in body
        assert parse_issue({"number": 1, "title": "TASK-001: x", "body": body}).depends_on == ()

    def test_human_authorization_is_carried_through(self):
        task = make_task("TASK-001", human_authorization=True, execution_mode="human")
        spec = parse_issue({"number": 1, "title": "TASK-001: x", "body": task.render_markdown()})
        assert spec.requires_human_execution

    def test_labels_match_the_repository_label_set(self):
        task = make_task("TASK-001", priority="P1", area="agent", task_type="research")
        assert set(task.labels) == {
            "type:research", "priority:P1", "status:ready",
            "area:agent", "execution:auto",
        }
