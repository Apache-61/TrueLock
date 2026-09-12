"""Path-budget enforcement (orchestrator/workers/scope.py).

CONTRIBUTING.md §4 gives each task a set of paths it may touch, and §6
makes "nothing else changed" part of done. These tests pin the three
rules that make that safe: forbidden beats allowed, an empty allow-list
permits nothing, and escapes never match.
"""
from __future__ import annotations

import pytest

from orchestrator.workers.scope import ScopeGuard, matches_any, normalize


class TestGlobMatching:
    @pytest.mark.parametrize("path", [
        "orchestrator/workers/cli.py",
        "orchestrator/workers/adapters/claude_code.py",
        "orchestrator/workers/deeply/nested/file.py",
    ])
    def test_double_star_crosses_directories(self, path):
        assert matches_any(path, ["orchestrator/workers/**"])

    def test_single_star_does_not_cross_directories(self):
        assert matches_any("detection/rules/duplicate.py", ["detection/rules/*.py"])
        assert not matches_any("detection/rules/sub/duplicate.py", ["detection/rules/*.py"])

    def test_bare_directory_covers_its_contents(self):
        assert matches_any("frontend/app/page.tsx", ["frontend/"])
        assert matches_any("frontend/app/page.tsx", ["frontend"])

    def test_exact_file_pattern(self):
        assert matches_any("docs/contracts/api.md", ["docs/contracts/api.md"])
        assert not matches_any("docs/contracts/case.md", ["docs/contracts/api.md"])

    def test_prefix_is_not_enough(self):
        """`domain/` must not match `domainsomething/`."""
        assert not matches_any("domainsomething/file.py", ["domain/**"])


class TestNormalize:
    @pytest.mark.parametrize("path", ["../outside.py", "/etc/passwd", "..", "a/../../b"])
    def test_escapes_normalize_to_empty(self, path):
        assert normalize(path) == ""

    def test_redundant_segments_are_collapsed(self):
        assert normalize("./orchestrator/./workers/../workers/cli.py") == (
            "orchestrator/workers/cli.py"
        )

    def test_backslashes_become_forward_slashes(self):
        assert normalize("orchestrator\\workers\\cli.py") == "orchestrator/workers/cli.py"


class TestScopeGuard:
    def guard(self):
        return ScopeGuard(
            ["orchestrator/workers/**", "scripts/orchestration/**"],
            ["domain/**", "agent/**"],
        )

    def test_in_scope_change_is_allowed(self):
        report = self.guard().check(["orchestrator/workers/runner.py"])
        assert report.ok
        assert report.allowed == ["orchestrator/workers/runner.py"]

    def test_forbidden_path_is_rejected(self):
        report = self.guard().check(["domain/schemas/invoice.schema.json"])
        assert not report.ok
        assert report.violations[0].rule == "forbidden"

    def test_path_outside_the_allow_list_is_rejected(self):
        report = self.guard().check(["frontend/app/page.tsx"])
        assert not report.ok
        assert report.violations[0].rule == "not-allowed"

    def test_forbidden_wins_when_a_path_matches_both_lists(self):
        """Overlap is a spec mistake; the safe reading is the strict one."""
        guard = ScopeGuard(["domain/**"], ["domain/schemas/**"])
        report = guard.check(["domain/schemas/lead.schema.json"])
        assert not report.ok
        assert report.violations[0].rule == "forbidden"

    def test_empty_allowed_paths_permits_nothing(self):
        """A task that forgot to declare paths must not become unbounded."""
        report = ScopeGuard([], []).check(["anything.py"])
        assert not report.ok
        assert "no allowed_paths" in report.violations[0].detail

    def test_escape_attempts_are_violations_not_matches(self):
        guard = ScopeGuard(["**"])
        report = guard.check(["../../etc/passwd", "/etc/shadow"])
        assert not report.ok
        assert {violation.rule for violation in report.violations} == {"escape"}

    def test_mixed_batch_reports_every_violation(self):
        report = self.guard().check([
            "orchestrator/workers/cli.py",
            "domain/entities/invoice.py",
            "frontend/app/page.tsx",
        ])
        assert not report.ok
        assert len(report.violations) == 2
        assert len(report.allowed) == 1

    def test_bookkeeping_paths_are_exempt(self):
        """The worker writes the handoff and timeline for every task; those
        are process artifacts, not part of the task's diff."""
        report = self.guard().check([
            "history/ai-activity/2026-09-12-task-007-run.md",
            "history/timeline.md",
        ])
        assert report.ok
        assert len(report.bookkeeping) == 2

    def test_bookkeeping_exemption_can_be_switched_off(self):
        report = self.guard().check(["history/timeline.md"], allow_bookkeeping=False)
        assert not report.ok

    def test_bookkeeping_does_not_smuggle_in_other_history_paths(self):
        """history/decisions/ is an ADR -- a human act, never exempt."""
        report = self.guard().check(["history/decisions/ADR-0005-something.md"])
        assert not report.ok

    def test_render_names_the_offending_paths(self):
        report = self.guard().check(["agent/runtime/loop.py"])
        rendered = report.render()
        assert "agent/runtime/loop.py" in rendered
        assert "forbidden" in rendered.lower()


class TestRealTaskBudgets:
    """TASK-007's own budget, as declared on its issue."""

    def setup_method(self):
        self.guard = ScopeGuard(
            ["orchestrator/workers/**", "orchestrator/routing/**",
             "orchestrator/policies/**", "scripts/orchestration/**"],
            ["domain/**", "detection/**", "agent/**", "frontend/**"],
        )

    @pytest.mark.parametrize("path", [
        "orchestrator/workers/runner.py",
        "orchestrator/routing/router.py",
        "orchestrator/policies/task-result.schema.json",
        "scripts/orchestration/worker.py",
    ])
    def test_worker_implementation_paths_are_in_scope(self, path):
        assert self.guard.check([path]).ok

    @pytest.mark.parametrize("path", [
        "domain/entities/invoice.py",
        "detection/rules/duplicate.py",
        "agent/runtime/loop.py",
        "frontend/app/page.tsx",
    ])
    def test_other_agents_areas_are_out_of_scope(self, path):
        assert not self.guard.check([path]).ok
