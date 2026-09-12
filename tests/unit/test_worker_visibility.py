"""The worker has to be legible while it works, and safe to interrupt.

Both of these were found by WORKER-01 on a real run. The worker reached
the AI step and then printed nothing at all for minutes: the CLI is
invoked with `capture_output=True` and `-p --output-format json`, so
nothing surfaces until it exits. The operator could not tell a working
worker from a hung one and pressed Ctrl+C, which is the rational
response to silence.

That exposed the second defect: the interrupt handler said "nothing
further was changed" while the CLAIM comment was already on the issue.
The task stayed locked to a worker that was no longer running until the
three-hour staleness window expired.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from orchestrator.workers.adapters.base import AIResult, SuiteResult
from orchestrator.workers.adapters.claude_code import ClaudeCodeAdapter
from orchestrator.workers.claim import find_winning_claim
from orchestrator.workers.config import WorkerConfig
from orchestrator.workers.github import FakeGitHubClient
from orchestrator.workers.gitops import Git
from orchestrator.workers.runner import WorkerRunner
from orchestrator.workers.safety import RunLimits
from orchestrator.workers.validation import GateResult, ValidationReport, Validator

TASK_BODY = """**Priority:** P0
**Depends on:** none
**Human authorization required:** No

**Objective:**
Add the ingestion normalizers.

**Allowed paths:**
- `domain/entities/**`

**Acceptance criteria:**
- [ ] It works
"""


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
    def run(self, *, changed_paths=None) -> ValidationReport:
        report = ValidationReport()
        report.add(GateResult("unit tests", "passed", "pytest", "3 passed"))
        return report


def build_runner(repo, client, adapter, log=None):
    config = WorkerConfig(
        worker_id="WORKER-01", repo_root=repo, owner="apache-61", repo="truelock",
        token="fake-token", base_branch="main",
    )
    return WorkerRunner(
        config, client, adapter,
        limits=RunLimits(once=True),
        git=Git(repo),
        validator=StubValidator(repo),
        log=log or (lambda *_: None),
    )


class InterruptingAdapter:
    """Stands in for the operator pressing Ctrl+C mid-run."""

    name = "interrupting"

    def execute(self, prompt, *, task_id, workdir, timeout=0, on_progress=None):
        raise KeyboardInterrupt()


class SilentAdapter:
    """An adapter that does not accept the progress callback."""

    name = "silent"

    def execute(self, prompt, *, task_id, workdir, timeout=0):
        return AIResult(task_id=task_id, status="DONE", summary="done",
                        changed_files=[], tests=SuiteResult(passed=1))


class TestAnInterruptDoesNotStrandTheTask:
    def test_ctrl_c_releases_the_claim(self, repo, client):
        runner = build_runner(repo, client, InterruptingAdapter())
        with pytest.raises(KeyboardInterrupt):
            runner.run()
        assert find_winning_claim(client.list_comments(1)) is None, (
            "the claim outlived the worker; the task is locked out of the queue "
            "until the staleness window expires"
        )

    def test_the_task_returns_to_ready(self, repo, client):
        runner = build_runner(repo, client, InterruptingAdapter())
        with pytest.raises(KeyboardInterrupt):
            runner.run()
        labels = {label["name"] for label in client.issues[1]["labels"]}
        assert "status:ready" in labels
        assert "status:claimed" not in labels

    def test_the_issue_says_what_happened(self, repo, client):
        runner = build_runner(repo, client, InterruptingAdapter())
        with pytest.raises(KeyboardInterrupt):
            runner.run()
        bodies = [comment["body"] for comment in client.list_comments(1)]
        assert any(body.startswith("WORKER ABANDONED") for body in bodies)

    def test_the_interrupt_still_propagates(self, repo, client):
        """Cleanup must not swallow the signal and keep the loop running."""
        runner = build_runner(repo, client, InterruptingAdapter())
        with pytest.raises(KeyboardInterrupt):
            runner.run()

    def test_cleanup_failures_do_not_mask_the_interrupt(self, repo, client):
        """A GitHub outage during cleanup must not replace the exception.

        The operator pressed Ctrl+C; that is what they need to see, not a
        RuntimeError from the tidying up afterwards.
        """
        real_add_comment = client.add_comment
        calls = {"n": 0}

        def flaky(number, body):
            calls["n"] += 1
            if calls["n"] == 1:  # the CLAIM itself must succeed
                return real_add_comment(number, body)
            raise RuntimeError("GitHub is down")

        client.add_comment = flaky
        runner = build_runner(repo, client, InterruptingAdapter())
        with pytest.raises(KeyboardInterrupt):
            runner.run()
        assert calls["n"] > 1, "cleanup never ran, so nothing was exercised"


class TestTheOperatorCanSeeItWorking:
    def test_the_run_announces_the_slow_step(self, repo, client):
        lines: list[str] = []
        runner = build_runner(repo, client, SilentAdapter(),
                              log=lambda *args: lines.append(" ".join(str(a) for a in args)))
        runner.run()
        assert any("prints nothing until it finishes" in line for line in lines), (
            "the operator gets no warning that the next step is silent and slow"
        )

    def test_an_adapter_without_the_callback_still_runs(self, repo, client):
        """The adapter protocol does not require on_progress."""
        summary = build_runner(repo, client, SilentAdapter()).run()
        assert summary.attempts and summary.attempts[0].outcome != "FAILED"

    def test_progress_is_reported_while_the_cli_runs(self, monkeypatch, tmp_path):
        """The heartbeat is what distinguishes 'thinking' from 'hung'."""
        import orchestrator.workers.adapters.claude_code as module

        monkeypatch.setattr(module, "HEARTBEAT_SECONDS", 0.01)

        def slow_run(command, **kwargs):
            time.sleep(0.1)
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

        monkeypatch.setattr(subprocess, "run", slow_run)
        adapter = ClaudeCodeAdapter()
        monkeypatch.setattr(adapter, "available", lambda: True)

        ticks: list[float] = []
        try:
            adapter.execute(
                "prompt", task_id="TASK-001", workdir=str(tmp_path),
                on_progress=lambda elapsed, budget: ticks.append(elapsed),
            )
        except Exception:
            pass  # the stub's envelope is not what this test is about
        assert ticks, "the CLI ran for 100ms with no heartbeat at a 10ms interval"

    def test_an_error_on_the_thread_reaches_the_caller(self, monkeypatch, tmp_path):
        """The work runs on a thread; a failure there must not vanish."""
        def exploding_run(command, **kwargs):
            raise OSError("cannot start the CLI")

        monkeypatch.setattr(subprocess, "run", exploding_run)
        adapter = ClaudeCodeAdapter()
        monkeypatch.setattr(adapter, "available", lambda: True)
        with pytest.raises(OSError):
            adapter.execute(
                "prompt", task_id="TASK-001", workdir=str(tmp_path),
                on_progress=lambda *_: None,
            )

    def test_a_timeout_on_the_thread_is_still_an_adapter_error(self, monkeypatch, tmp_path):
        from orchestrator.workers.adapters.base import AdapterError

        def timing_out(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)

        monkeypatch.setattr(subprocess, "run", timing_out)
        adapter = ClaudeCodeAdapter()
        monkeypatch.setattr(adapter, "available", lambda: True)
        with pytest.raises(AdapterError) as caught:
            adapter.execute(
                "prompt", task_id="TASK-001", workdir=str(tmp_path), timeout=1,
                on_progress=lambda *_: None,
            )
        assert "budget" in str(caught.value)
