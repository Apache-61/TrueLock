"""A failed run must leave the machine able to try again.

Found on a Windows workstation running the real CLI. One transient
failure wedged the worker permanently, and the mechanism was entirely
self-inflicted:

1. The adapter wrote the prompt to the CLI's stdin using the platform's
   preferred encoding. On Windows that is cp1252, the prompt carries the
   repository's own documents (protocol arrows and all), and
   `stdin.write` raised `UnicodeEncodeError` on subprocess's writer
   *thread* -- so `run` did not raise, the CLI just got no input and
   exited 1.
2. The failure path then wrote `history/ai-activity/<run>.md` and
   appended to `history/timeline.md`, both tracked, and committed
   neither.
3. The next run refused to start: "working tree is dirty". That failure
   wrote *another* pair of artifacts. Every subsequent attempt failed the
   same way, for a reason the worker had created itself.

The operator had to hand-clean the tree and relabel the issue three
times, and in `--continuous` this trips the three-failure circuit
breaker with two failures the worker caused.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from orchestrator.workers.adapters.base import AIResult
from orchestrator.workers.adapters.claude_code import ClaudeCodeAdapter
from orchestrator.workers.config import WorkerConfig
from orchestrator.workers.github import FakeGitHubClient
from orchestrator.workers.gitops import Git
from orchestrator.workers.handoff import Handoff
from orchestrator.workers.runner import Outcome, WorkerRunner
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
    (root / ".gitignore").write_text(".state/\n")
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


class ExplodingAdapter:
    """An adapter that fails the way the real CLI did."""

    name = "exploding"

    def execute(self, prompt, *, task_id, workdir, timeout=0):
        from orchestrator.workers.adapters.base import AdapterError

        raise AdapterError(
            f"the Claude Code CLI exited 1 for {task_id}: Error: Input must be "
            "provided either through stdin or as a prompt argument"
        )


def build_runner(repo, client, adapter):
    config = WorkerConfig(
        worker_id="WORKER-01", repo_root=repo, owner="apache-61", repo="truelock",
        token="fake-token", base_branch="main",
    )
    return WorkerRunner(
        config, client, adapter,
        limits=RunLimits(once=True),
        git=Git(repo),
        validator=StubValidator(repo),
        log=lambda *_: None,
    )


def dirty_paths(repo: Path) -> list[str]:
    """Everything git considers uncommitted, ignored files excluded."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True
    )
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


class TestAFailedRunLeavesTheTreeClean:
    def test_an_adapter_failure_leaves_nothing_uncommitted(self, repo, client):
        summary = build_runner(repo, client, ExplodingAdapter()).run()
        assert summary.attempts[0].outcome == Outcome.FAILED
        assert dirty_paths(repo) == [], (
            "a failed run left files behind; the next run will refuse to start "
            "on a dirty tree and fail for a reason the worker created itself"
        )

    def test_a_second_run_can_still_start_after_a_failure(self, repo, client):
        """The regression that actually cost the operator time."""
        build_runner(repo, client, ExplodingAdapter()).run()
        second = build_runner(repo, client, ExplodingAdapter()).run()
        reason = second.attempts[0].reason if second.attempts else second.stop_reason
        assert "dirty" not in reason.lower(), (
            f"the second run failed on the first run's leftovers: {reason}"
        )

    def test_the_handoff_still_exists_for_debugging(self, repo, client):
        """Clean must not mean the failure went unrecorded."""
        build_runner(repo, client, ExplodingAdapter()).run()
        records = list((repo / ".state").glob("task-result-*.json"))
        assert records, "the failure left no handoff record at all"

    def test_the_checkout_returns_to_the_base_branch(self, repo, client):
        build_runner(repo, client, ExplodingAdapter()).run()
        branch = subprocess.run(
            ["git", "branch", "--show-current"], cwd=repo,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert branch == "main", (
            f"left on {branch}; the next run would start from a half-finished branch"
        )

    def test_state_only_writes_no_history_entry(self, repo):
        handoff = Handoff(
            run_id="AI-RUN-TEST", worker_id="WORKER-01", task_id="TASK-001",
            issue_number=1, branch="feature/x", started_at="2026-09-12T00:00:00Z",
            goal="x", result=AIResult(task_id="TASK-001", status="FAILED", summary="no"),
        )
        written = handoff.write(repo, state_only=True)
        assert "history" not in written
        assert not list((repo / "history" / "ai-activity").glob("*.md"))
        assert written["task_result"].is_file()


class TestAnInfrastructureFailureDoesNotBlockTheTask:
    def test_the_task_returns_to_ready_not_blocked(self, repo, client):
        """BLOCKED is terminal, so a flaky run would drop a P0 task from the queue."""
        build_runner(repo, client, ExplodingAdapter()).run()
        labels = {label["name"] for label in client.issues[1]["labels"]}
        assert "status:ready" in labels
        assert "status:blocked" not in labels

    def test_the_claim_is_released(self, repo, client):
        from orchestrator.workers.claim import find_winning_claim

        build_runner(repo, client, ExplodingAdapter()).run()
        assert find_winning_claim(client.list_comments(1)) is None

    def test_a_task_level_failure_still_blocks(self, repo, client):
        """Only infrastructure is retried; a real problem still wants a human."""
        runner = build_runner(repo, client, ExplodingAdapter())
        assert runner._is_infrastructure_failure("adapter error: exited 1")
        assert runner._is_infrastructure_failure("branch creation failed: dirty")
        assert runner._is_infrastructure_failure("push failed: rejected")
        assert not runner._is_infrastructure_failure(
            "validation failed: 3 tests failed"
        )


class TestTheAdapterTalksUtf8:
    def test_the_cli_is_invoked_with_an_explicit_encoding(self, monkeypatch, tmp_path):
        """Without this, Windows uses cp1252 and the prompt cannot be written."""
        captured = {}

        def fake_run(command, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

        adapter = ClaudeCodeAdapter()
        monkeypatch.setattr(adapter, "available", lambda: True)
        monkeypatch.setattr(subprocess, "run", fake_run)
        try:
            adapter.execute("prompt", task_id="TASK-001", workdir=str(tmp_path))
        except Exception:
            pass  # parsing the stub's output is not what this test is about
        assert captured.get("encoding") == "utf-8"

    def test_a_non_ascii_prompt_survives_the_round_trip(self, monkeypatch, tmp_path):
        """The real prompt carries the repository's own documents."""
        prompt = "TASK → CLAIM → BRANCH → CLAUDE — ADR §5 ✓"
        seen = {}

        def fake_run(command, **kwargs):
            seen["input"] = kwargs.get("input")
            encoded = kwargs["input"].encode(kwargs["encoding"])
            assert encoded.decode(kwargs["encoding"]) == prompt
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

        adapter = ClaudeCodeAdapter()
        monkeypatch.setattr(adapter, "available", lambda: True)
        monkeypatch.setattr(subprocess, "run", fake_run)
        try:
            adapter.execute(prompt, task_id="TASK-001", workdir=str(tmp_path))
        except Exception:
            pass
        assert seen["input"] == prompt

    def test_this_repository_really_does_feed_non_ascii_into_the_prompt(self):
        """Guards the assumption above.

        If the context pack were pure ASCII none of this would matter and
        the encoding fix could be quietly dropped. It is not: the worker
        builds its prompt from this repository's own documents, and they
        are full of arrows, section signs and em dashes.
        """
        root = Path(__file__).resolve().parents[2]
        sources = [
            root / "orchestrator" / "README.md",
            root / "CONTRIBUTING.md",
            root / "docs" / "contracts" / "domain.md",
        ]
        offenders = [
            path.name
            for path in sources
            if path.is_file() and not path.read_text(encoding="utf-8").isascii()
        ]
        assert offenders, (
            "no context document contains non-ASCII text; the Windows "
            "encoding failure needs it to reproduce"
        )
