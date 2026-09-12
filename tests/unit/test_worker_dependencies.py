"""The eligibility gate (orchestrator/workers/dependencies.py).

A task may only run when it is READY, authorized, unblocked, unclaimed,
and all of its dependencies are actually merged. The interesting cases
are the conservative ones: an unknown dependency counts as unmet, not as
satisfied.
"""
from __future__ import annotations

import pytest

from orchestrator.workers.claim import format_claim
from orchestrator.workers.dependencies import build_task_index, check_eligibility
from orchestrator.workers.tasks import parse_issue


def issue(number, task_id, body="", labels=None, state="open"):
    return {
        "number": number,
        "title": f"{task_id}: title",
        "body": body or "**Priority:** P0\n**Depends on:** none\n",
        "state": state,
        "labels": [{"name": name} for name in (labels or [])],
    }


def spec(number=2, depends="TASK-001", labels=None, state="open", extra=""):
    body = f"**Priority:** P0\n**Depends on:** {depends}\n{extra}"
    return parse_issue(issue(number, f"TASK-{number:03d}", body, labels, state))


class TestDependencySatisfaction:
    def test_closed_dependency_is_satisfied(self):
        index = build_task_index([issue(1, "TASK-001", state="closed")])
        assert check_eligibility(spec(), task_index=index).eligible

    def test_status_done_label_is_satisfied(self):
        index = build_task_index([issue(1, "TASK-001", labels=["status:done"])])
        assert check_eligibility(spec(), task_index=index).eligible

    def test_merged_status_in_body_is_satisfied(self):
        index = build_task_index([issue(1, "TASK-001", body="- **status:** MERGED\n")])
        assert check_eligibility(spec(), task_index=index).eligible

    def test_open_ready_dependency_is_not_satisfied(self):
        index = build_task_index([issue(1, "TASK-001", labels=["status:ready"])])
        result = check_eligibility(spec(), task_index=index)
        assert not result.eligible
        assert result.unmet_dependencies == ("TASK-001",)

    def test_in_review_dependency_is_not_satisfied(self):
        """READY_FOR_REVIEW means a PR is open, not that it merged."""
        index = build_task_index([issue(1, "TASK-001", labels=["status:review"])])
        assert not check_eligibility(spec(), task_index=index).eligible

    def test_unknown_dependency_is_treated_as_unmet(self):
        """Silence is not consent: a dependency we cannot see might not
        have merged, and building on it produces an unreviewable PR."""
        result = check_eligibility(spec(depends="TASK-042"), task_index={})
        assert not result.eligible
        assert "no matching issue found" in result.reason

    def test_all_dependencies_must_be_satisfied(self):
        index = build_task_index([
            issue(1, "TASK-001", state="closed"),
            issue(3, "TASK-003", labels=["status:ready"]),
        ])
        result = check_eligibility(spec(number=4, depends="TASK-001, TASK-003"), task_index=index)
        assert not result.eligible
        assert result.unmet_dependencies == ("TASK-003",)

    def test_no_dependencies_is_eligible(self):
        assert check_eligibility(spec(depends="none"), task_index={}).eligible


class TestStateGates:
    @pytest.mark.parametrize("label", ["status:blocked"])
    def test_blocked_task_is_not_eligible(self, label):
        result = check_eligibility(spec(depends="none", labels=[label]), task_index={})
        assert not result.eligible
        assert "BLOCKED" in result.reason

    def test_closed_issue_is_not_eligible(self):
        result = check_eligibility(spec(depends="none", state="closed"), task_index={})
        assert not result.eligible
        assert "closed" in result.reason

    @pytest.mark.parametrize("status", ["RESEARCH", "PROPOSAL", "WAITING_AUTHORIZATION"])
    def test_unauthorized_states_are_refused_with_the_rule_cited(self, status):
        task = spec(depends="none", extra=f"- **status:** {status}\n")
        result = check_eligibility(task, task_index={})
        assert not result.eligible
        assert "not authorized" in result.reason

    def test_already_merged_task_is_not_re_run(self):
        task = spec(depends="none", extra="- **status:** MERGED\n")
        assert not check_eligibility(task, task_index={}).eligible


class TestClaimGate:
    def test_task_claimed_by_another_worker_is_not_eligible(self):
        comments = [{"id": 1, "body": format_claim("TASK-002", "WORKER-09", "c", "t")}]
        result = check_eligibility(
            spec(depends="none"), task_index={}, comments=comments, worker_id="WORKER-01"
        )
        assert not result.eligible
        assert result.blocking_worker == "WORKER-09"

    def test_our_own_claim_does_not_block_us(self):
        """Resuming our own claimed task is legitimate; blocking on it
        would strand the task after any interruption."""
        comments = [{"id": 1, "body": format_claim("TASK-002", "WORKER-01", "c", "t")}]
        result = check_eligibility(
            spec(depends="none"), task_index={}, comments=comments, worker_id="WORKER-01"
        )
        assert result.eligible

    def test_released_claim_does_not_block(self):
        comments = [
            {"id": 1, "body": format_claim("TASK-002", "WORKER-09", "c", "t")},
            {"id": 2, "body": "RELEASE\nworker_id: WORKER-09\n"},
        ]
        result = check_eligibility(
            spec(depends="none"), task_index={}, comments=comments, worker_id="WORKER-01"
        )
        assert result.eligible


class TestRealDependencyGraph:
    """The seeded queue: TASK-001 and TASK-006 are startable, the rest wait."""

    def setup_method(self):
        self.issues = [
            issue(1, "TASK-001", "**Priority:** P0\n**Depends on:** none\n"),
            issue(2, "TASK-002", "**Priority:** P0\n**Depends on:** TASK-001\n"),
            issue(3, "TASK-003", "**Priority:** P0\n**Depends on:** TASK-001\n"),
            issue(4, "TASK-004", "**Priority:** P0\n**Depends on:** TASK-001, TASK-003\n"),
            issue(6, "TASK-006", "**Priority:** P0\n**Depends on:** none\n"),
        ]
        self.index = build_task_index(self.issues)

    def test_only_root_tasks_are_startable_initially(self):
        eligible = [
            parse_issue(raw).task_id
            for raw in self.issues
            if check_eligibility(parse_issue(raw), task_index=self.index).eligible
        ]
        assert eligible == ["TASK-001", "TASK-006"]

    def test_merging_the_root_unblocks_its_dependents(self):
        self.issues[0]["state"] = "closed"
        index = build_task_index(self.issues)
        eligible = [
            parse_issue(raw).task_id
            for raw in self.issues
            if check_eligibility(parse_issue(raw), task_index=index).eligible
        ]
        assert eligible == ["TASK-002", "TASK-003", "TASK-006"]
        assert "TASK-004" not in eligible  # still waiting on TASK-003
