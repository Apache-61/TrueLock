"""The continuous production loop (`--continuous`).

These cover the difference between "a worker that can do one task" and
"four machines that keep working for a day without duplicating each
other". Each test corresponds to a way the previous loop stalled or
collided:

* a merged PR never closed its issue, so nothing that depended on it ever
  became eligible -- with a 7-deep graph, all four machines would have
  gone idle behind the first wave;
* a BLOCKED task ended the whole run, idling a machine for an outcome
  that is expected and already explained on the issue;
* an empty queue exited, when most work here unlocks only when a human
  merges something;
* a crashed worker's claim was held forever, stranding the task;
* nothing bounded a machine that was failing every task it touched.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestrator.workers import completion
from orchestrator.workers.claim import (
    Claim,
    claim_age_minutes,
    find_winning_claim,
    format_claim,
    stale_claim,
)
from orchestrator.workers.config import WorkerConfig
from orchestrator.workers.dependencies import build_task_index, check_eligibility
from orchestrator.workers.github import FakeGitHubClient
from orchestrator.workers.gitops import Git
from orchestrator.workers.runner import Outcome, WorkerRunner
from orchestrator.workers.safety import RunLimits
from orchestrator.workers.tasks import parse_issue
from orchestrator.workers.validation import GateResult, ValidationReport, Validator
from orchestrator.workers.adapters.base import AIResult, SuiteResult
from orchestrator.workers.adapters.mock import MockAdapter

TASK_BODY = """**Priority:** P0
**Depends on:** none
**Human authorization required:** No

**Objective:**
Add the ingestion normalizers.

**Allowed paths:**
- `domain/entities/**`

**Forbidden paths:**
- `domain/schemas/**`

**Acceptance criteria:**
- [ ] It works
"""

DEPENDENT_BODY = TASK_BODY.replace("**Depends on:** none", "**Depends on:** TASK-001")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    root = tmp_path / "clone"
    root.mkdir()

    def run(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    run("init", "-b", "main")
    run("config", "user.email", "worker@example.com")
    run("config", "user.name", "Worker")
    (root / "README.md").write_text("# fixture\n")
    (root / "domain" / "entities").mkdir(parents=True)
    (root / "history" / "ai-activity").mkdir(parents=True)
    (root / "history" / "timeline.md").write_text("# Timeline\n")
    run("add", "-A")
    run("commit", "-m", "initial")
    run("remote", "add", "origin", str(origin))
    run("push", "-u", "origin", "main")
    return root


@pytest.fixture
def client() -> FakeGitHubClient:
    fake = FakeGitHubClient()
    fake.add_issue(1, "TASK-001: Canonical ingestion", TASK_BODY, ["status:ready"])
    return fake


class StubValidator(Validator):
    def __init__(self, repo_root: Path, *, ok: bool = True) -> None:
        super().__init__(repo_root)
        self._ok = ok

    def run(self, *, changed_paths=None) -> ValidationReport:
        report = ValidationReport()
        report.add(GateResult(
            "unit tests (pytest tests/unit)",
            "passed" if self._ok else "failed",
            "pytest -q tests/unit",
            "3 passed in 0.1s" if self._ok else "1 failed, 2 passed in 0.1s",
        ))
        return report


class WritingAdapter(MockAdapter):
    def __init__(self, files: dict[str, str], status: str = "DONE") -> None:
        super().__init__()
        self.files = files
        self.status = status

    def execute(self, prompt, *, task_id, workdir, timeout=0):
        self.last_prompt = prompt
        for relative, content in self.files.items():
            path = Path(workdir) / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return AIResult(
            task_id=task_id, status=self.status, summary="Wrote the requested files.",
            changed_files=list(self.files), tests=SuiteResult(passed=3),
        )


class RecordingSleep:
    """Stands in for time.sleep so idle waits are instant and inspectable."""

    def __init__(self, stop_after: int = 0) -> None:
        self.calls: list[float] = []
        self.stop_after = stop_after

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if self.stop_after and len(self.calls) >= self.stop_after:
            raise KeyboardInterrupt("test: stop the idle loop")


def build_runner(repo, client, *, adapter=None, ok=True, limits=None, sleep=None,
                 **config_kwargs):
    defaults = dict(
        worker_id="WORKER-01", repo_root=repo, owner="apache-61", repo="truelock",
        token="fake-token", base_branch="main",
    )
    defaults.update(config_kwargs)
    config = WorkerConfig(**defaults)
    return WorkerRunner(
        config,
        client,
        adapter or MockAdapter(write_files=True),
        limits=limits or RunLimits(once=True),
        git=Git(repo),
        validator=StubValidator(repo, ok=ok),
        log=lambda *_: None,
        sleep=sleep or (lambda _seconds: None),
    )


def continuous(**kwargs) -> RunLimits:
    """The limits `worker start --continuous` builds."""
    base = dict(
        once=False,
        poll_when_idle=True,
        stop_on_blocker=False,
        max_tasks=5,
        # So a test that exhausts its queue terminates. A real
        # continuous worker waits indefinitely by design; that is what
        # test_an_empty_queue_waits_instead_of_exiting covers, by
        # bounding the run with a sleep that raises instead.
        max_idle_minutes=0.0001,
    )
    base.update(kwargs)
    return RunLimits(**base)


class TestMergedWorkUnlocksDependants:
    """Steps 14-17. Without this the queue stalls behind the first wave."""

    def test_a_merged_pull_request_closes_its_task(self, client):
        client.issues[1]["labels"] = [{"name": "status:review"}]
        client.pulls.append({
            "number": 5, "head": "feature/TASK-001-canonical-ingestion",
            "state": "closed", "merged": True,
            "html_url": "https://github.com/apache-61/truelock/pull/5",
        })
        task = parse_issue(client.get_issue(1))
        outcome = completion.reconcile_task(client, task, worker_id="WORKER-01",
                                            log=lambda *_: None)
        assert outcome == "completed"
        assert client.issues[1]["state"] == "closed"
        assert "status:done" in {label["name"] for label in client.issues[1]["labels"]}

    def test_closing_the_dependency_makes_the_dependant_eligible(self, client):
        """The actual unlock, asserted through the real eligibility gate."""
        client.add_issue(2, "TASK-002: Database", DEPENDENT_BODY, ["status:ready"])

        def eligible_now() -> bool:
            issues = client.list_issues(state="all")
            index = build_task_index(issues)
            task = parse_issue(client.get_issue(2))
            return check_eligibility(task, task_index=index,
                                     comments=client.list_comments(2)).eligible

        assert not eligible_now(), "TASK-002 must wait for TASK-001"

        client.issues[1]["labels"] = [{"name": "status:review"}]
        client.pulls.append({
            "number": 5, "head": "feature/TASK-001-canonical-ingestion",
            "state": "closed", "merged": True, "html_url": "http://pr/5",
        })
        completion.reconcile_task(client, parse_issue(client.get_issue(1)),
                                  worker_id="WORKER-01", log=lambda *_: None)

        assert eligible_now(), "closing TASK-001 must unlock TASK-002"

    def test_reconciling_twice_does_not_comment_twice(self, client):
        client.issues[1]["labels"] = [{"name": "status:review"}]
        client.pulls.append({
            "number": 5, "head": "feature/TASK-001-canonical-ingestion",
            "state": "closed", "merged": True, "html_url": "http://pr/5",
        })
        task = parse_issue(client.get_issue(1))
        first = completion.reconcile_task(client, task, worker_id="W", log=lambda *_: None)
        second = completion.reconcile_task(client, task, worker_id="W", log=lambda *_: None)
        assert (first, second) == ("completed", "")
        markers = [comment for comment in client.list_comments(1)
                   if completion.COMPLETION_MARKER in comment["body"]]
        assert len(markers) == 1

    def test_a_pull_request_closed_unmerged_returns_the_task_to_the_queue(self, client):
        client.issues[1]["labels"] = [{"name": "status:review"}]
        client.add_comment(1, format_claim("TASK-001", "WORKER-02", "cid", "2026-09-12T00:00:00Z"))
        client.pulls.append({
            "number": 5, "head": "feature/TASK-001-canonical-ingestion",
            "state": "closed", "merged": False, "html_url": "http://pr/5",
        })
        outcome = completion.reconcile_task(client, parse_issue(client.get_issue(1)),
                                            worker_id="WORKER-01", log=lambda *_: None)
        assert outcome == "returned"
        assert client.issues[1]["state"] == "open", "an unmerged task is not done"
        assert find_winning_claim(client.list_comments(1)) is None, "the claim must be released"

    def test_an_open_pull_request_is_left_alone(self, client):
        client.issues[1]["labels"] = [{"name": "status:review"}]
        client.pulls.append({
            "number": 5, "head": "feature/TASK-001-canonical-ingestion",
            "state": "open", "merged": False, "html_url": "http://pr/5",
        })
        outcome = completion.reconcile_task(client, parse_issue(client.get_issue(1)),
                                            worker_id="W", log=lambda *_: None)
        assert outcome == ""
        assert client.issues[1]["state"] == "open"


class TestTheLoopKeepsGoing:
    def test_a_blocker_no_longer_ends_a_continuous_run(self, repo, client):
        """The issue carries the explanation; the machine keeps working."""
        client.add_issue(2, "TASK-002: Second", TASK_BODY, ["status:ready"])
        adapter = WritingAdapter({"frontend/app.tsx": "out of scope\n"})
        summary = build_runner(repo, client, adapter=adapter, limits=continuous()).run()
        assert [attempt.outcome for attempt in summary.attempts] == [
            Outcome.BLOCKED, Outcome.BLOCKED,
        ]

    def test_once_still_stops_on_a_blocker(self, repo, client):
        """The original guarantee is unchanged for an attended run."""
        client.add_issue(2, "TASK-002: Second", TASK_BODY, ["status:ready"])
        adapter = WritingAdapter({"frontend/app.tsx": "out of scope\n"})
        summary = build_runner(repo, client, adapter=adapter,
                               limits=RunLimits(max_tasks=5)).run()
        assert len(summary.attempts) == 1
        assert "BLOCKED" in summary.stop_reason

    def test_an_empty_queue_waits_instead_of_exiting(self, repo, client):
        client.issues[1]["state"] = "closed"
        sleep = RecordingSleep(stop_after=3)
        runner = build_runner(repo, client, limits=continuous(), sleep=sleep)
        with pytest.raises(KeyboardInterrupt):
            runner.run()
        assert len(sleep.calls) == 3, "an idle continuous worker polls, it does not exit"

    def test_idle_waits_are_jittered(self, repo, client):
        """Four machines polling in lockstep race for the same task."""
        client.issues[1]["state"] = "closed"
        sleep = RecordingSleep(stop_after=8)
        runner = build_runner(repo, client, limits=continuous(), sleep=sleep,
                              poll_seconds=100.0)
        with pytest.raises(KeyboardInterrupt):
            runner.run()
        assert len(set(sleep.calls)) > 1, "every wait was identical; no jitter"
        assert all(60 <= delay <= 140 for delay in sleep.calls), sleep.calls

    def test_max_idle_stops_a_worker_with_nothing_to_do(self, repo, client):
        client.issues[1]["state"] = "closed"
        limits = continuous(max_idle_minutes=0.0001)
        summary = build_runner(repo, client, limits=limits,
                               sleep=lambda _s: None).run()
        assert "max-idle" in summary.stop_reason

    def test_consecutive_failures_stop_the_machine(self, repo, client):
        """A machine failing unrelated tasks is usually itself the fault."""
        for number in (2, 3, 4, 5):
            client.add_issue(number, f"TASK-00{number}: Task", TASK_BODY, ["status:ready"])
        adapter = WritingAdapter({"domain/entities/invoice.py": "x\n"})
        limits = continuous(max_tasks=0, max_failure_streak=3)
        summary = build_runner(repo, client, adapter=adapter, ok=False, limits=limits).run()
        assert len(summary.attempts) == 3
        assert all(attempt.outcome == Outcome.FAILED for attempt in summary.attempts)
        assert "failed in a row" in summary.stop_reason

    def test_a_success_resets_the_failure_streak(self):
        limits = RunLimits(max_failure_streak=3)
        limits.record_outcome(failed=True)
        limits.record_outcome(failed=True)
        limits.record_outcome(failed=False)
        limits.record_outcome(failed=True)
        assert limits.stop_reason() == "", "two failures either side of a success is not a streak"


class TestStaleClaimsAreRecovered:
    def _comments(self, *, minutes_old: float) -> list[dict]:
        stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes_old)).isoformat()
        return [{"id": 1, "body": format_claim("TASK-001", "WORKER-09", "abandoned", stamp)}]

    def test_a_fresh_claim_is_respected(self):
        comments = self._comments(minutes_old=5)
        winner = find_winning_claim(comments, stale_after_minutes=180)
        assert winner is not None and winner.worker_id == "WORKER-09"

    def test_a_silent_claim_expires(self):
        comments = self._comments(minutes_old=400)
        assert find_winning_claim(comments, stale_after_minutes=180) is None

    def test_expiry_is_off_by_default(self):
        """The protocol's guarantee is unchanged unless staleness is asked for."""
        comments = self._comments(minutes_old=4000)
        assert find_winning_claim(comments) is not None

    def test_later_activity_keeps_a_claim_alive(self):
        """A worker posting progress is evidence it has not crashed."""
        comments = self._comments(minutes_old=400)
        comments.append({"id": 2, "body": "WORKER UPDATE\nstill working"})
        winner = find_winning_claim(comments, stale_after_minutes=180)
        assert winner is not None and winner.worker_id == "WORKER-09"

    def test_a_takeover_is_reported(self):
        comments = self._comments(minutes_old=400)
        abandoned = stale_claim(comments, stale_after_minutes=180)
        assert abandoned is not None and abandoned.worker_id == "WORKER-09"

    def test_an_unparseable_timestamp_is_not_treated_as_ancient(self):
        """A malformed claim must not be stolen instantly."""
        claim = Claim("TASK-001", "WORKER-09", "cid", "not-a-date", 1)
        assert claim_age_minutes(claim) == 0.0

    def test_the_worker_takes_over_a_stale_claim_and_says_so(self, repo, client):
        stamp = (datetime.now(timezone.utc) - timedelta(minutes=400)).isoformat()
        client.add_comment(1, format_claim("TASK-001", "WORKER-09", "abandoned", stamp))
        adapter = WritingAdapter({"domain/entities/invoice.py": "x\n"})
        summary = build_runner(repo, client, adapter=adapter,
                               claim_stale_minutes=180.0).run()
        assert summary.attempts[0].outcome == Outcome.DONE
        bodies = [comment["body"] for comment in client.list_comments(1)]
        # The takeover is recorded as a RELEASE -- the protocol's own
        # primitive -- so a human reading the thread, and task_cli.py,
        # both see it without needing a special case.
        release = next(body for body in bodies if body.startswith("RELEASE"))
        assert "expired" in release
        assert "WORKER-09" in release
        assert "released_by: WORKER-01" in release

    def test_a_live_claim_still_blocks_another_worker(self, repo, client):
        """The load-bearing property: staleness must not weaken this."""
        client.add_comment(1, format_claim("TASK-001", "WORKER-09", "live",
                                           datetime.now(timezone.utc).isoformat()))
        summary = build_runner(repo, client, claim_stale_minutes=180.0).run()
        assert summary.attempts == []
        assert "already claimed by WORKER-09" in summary.stop_reason
