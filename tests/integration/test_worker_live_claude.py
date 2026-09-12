"""The worker against the REAL Claude Code CLI.

Opt-in, because it calls a paid API and takes minutes:

    WORKER_LIVE_AI_TEST=1 pytest -q tests/integration/test_worker_live_claude.py

Skipped otherwise — including in CI, which must stay free and fast
(`.github/workflows/ci.yml`). Everything else about the loop is covered
offline in `tests/unit/test_worker_loop.py`; what only a live run can
prove is that the CLI is invoked correctly, that its JSON envelope parses
into a valid result, and that real usage lands in the ledger.

The GitHub side stays in-memory even here: this test may call a real
model, but it never touches the real repository.

Two bugs were found by running this for the first time, and both are now
pinned by unit tests as well: the worker promoted a self-declared PARTIAL
to DONE when the tests happened to pass, and it opened a normal PR for a
run the AI had explicitly flagged for human review.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from orchestrator.workers.adapters.claude_code import ClaudeCodeAdapter
from orchestrator.workers.config import WorkerConfig
from orchestrator.workers.github import FakeGitHubClient
from orchestrator.workers.gitops import Git
from orchestrator.workers.runner import Outcome, WorkerRunner
from orchestrator.workers.safety import RunLimits
from orchestrator.workers.validation import Validator

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("WORKER_LIVE_AI_TEST") != "1",
        reason="live AI test: set WORKER_LIVE_AI_TEST=1 to run (calls a paid API)",
    ),
    pytest.mark.skipif(
        not ClaudeCodeAdapter().available(),
        reason="the Claude Code CLI is not installed on this machine",
    ),
]

TASK_BODY = """**Priority:** P0
**Depends on:** none
**Human authorization required:** No

**Objective:**
Add a `mathutils/stats.py` module with a `median(values)` function that
returns the median of a list of numbers. It must raise `ValueError` on an
empty list, and handle both odd and even length lists. Add unit tests in
`tests/unit/test_stats.py`.

**Allowed paths:**
- `mathutils/**`
- `tests/unit/**`

**Forbidden paths:**
- `README.md`

**Acceptance criteria:**
- [ ] `median` works for odd-length and even-length input
- [ ] An empty list raises ValueError rather than returning None
"""


@pytest.fixture(scope="module")
def live_run(tmp_path_factory):
    """One real run, shared by every assertion below.

    Module-scoped on purpose: the AI call costs real money and minutes,
    so the suite pays for it once and then interrogates the result.
    """
    sandbox = tmp_path_factory.mktemp("live")
    origin = sandbox / "origin.git"
    root = sandbox / "clone"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    root.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    (root / "mathutils").mkdir()
    (root / "mathutils" / "__init__.py").write_text("")
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "test_smoke.py").write_text("def test_smoke():\n    assert True\n")
    (root / "history" / "ai-activity").mkdir(parents=True)
    (root / "history" / "timeline.md").write_text("# Timeline\n")
    (root / "README.md").write_text("# sandbox\n")
    # Without this the sandbox's own package is not importable and the
    # AI's (correct) tests fail to collect -- a fixture problem, not a
    # worker problem. Discovered the hard way on the first live run.
    (root / "conftest.py").write_text("# makes the sandbox package importable\n")

    git("init", "-b", "main")
    git("config", "user.email", "worker@example.com")
    git("config", "user.name", "Worker")
    git("add", "-A")
    git("commit", "-m", "initial")
    git("remote", "add", "origin", str(origin))
    git("push", "-u", "origin", "main")

    client = FakeGitHubClient()
    client.add_issue(1, "TASK-001: Median helper", TASK_BODY, ["status:ready"])

    config = WorkerConfig(
        worker_id="WORKER-LIVE", repo_root=root, owner="apache-61", repo="truelock",
        token="not-used-by-the-in-memory-client", base_branch="main",
    )
    adapter = ClaudeCodeAdapter()
    runner = WorkerRunner(
        config, client, adapter,
        limits=RunLimits(once=True),
        git=Git(root),
        validator=Validator(root, timeout=600),
        log=lambda *_: None,
    )
    summary = runner.run()
    return {"summary": summary, "client": client, "runner": runner,
            "root": root, "adapter": adapter}


class TestLiveLoop:
    def test_the_loop_completes_without_an_adapter_error(self, live_run):
        attempt = live_run["summary"].attempts[0]
        assert attempt.outcome in (Outcome.DONE, Outcome.PARTIAL), attempt.reason

    def test_the_ai_actually_wrote_the_requested_module(self, live_run):
        assert (live_run["root"] / "mathutils" / "stats.py").is_file()

    def test_the_implementation_is_correct(self, live_run):
        """Run the AI's own code, rather than trusting its status."""
        import importlib.util

        path = live_run["root"] / "mathutils" / "stats.py"
        spec = importlib.util.spec_from_file_location("live_stats", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.median([3, 1, 2]) == 2
        assert module.median([1, 2, 3, 4]) == 2.5
        with pytest.raises(ValueError):
            module.median([])

    def test_it_stayed_inside_the_allowed_paths(self, live_run):
        changed = Git(live_run["root"]).run(
            "diff", "--name-only", "main...HEAD"
        ).stdout.split()
        assert changed, "the AI changed nothing"
        for path in changed:
            # mathutils/ and tests/unit/ are the task's budget;
            # history/ is the bookkeeping every task writes.
            assert path.startswith(("mathutils/", "tests/unit/", "history/")), path
        assert "README.md" not in changed

    def test_worker_scratch_did_not_reach_the_branch(self, live_run):
        """`.state/` is runtime scratch and must stay out of the PR even
        in a repository whose .gitignore does not mention it."""
        committed = Git(live_run["root"]).run(
            "diff", "--name-only", "main...HEAD"
        ).stdout.split()
        assert not [path for path in committed if path.startswith(".state/")]

    def test_a_pull_request_was_opened_and_not_merged(self, live_run):
        pulls = live_run["client"].pulls
        assert len(pulls) == 1
        assert pulls[0]["base"] == "main"
        assert not any("merge" in call.path.lower() for call in live_run["client"].recorded)

    def test_real_usage_reached_the_ledger(self, live_run):
        entries = live_run["runner"].ledger.entries
        assert len(entries) == 1
        entry = entries[0]
        assert entry.status == "ok"
        assert entry.model and entry.model != "default", "the served model was not captured"
        assert (entry.input_tokens or 0) > 0
        assert (entry.output_tokens or 0) > 0

    def test_the_handoff_and_history_were_written(self, live_run):
        root = live_run["root"]
        assert list((root / ".state").glob("task-result-*.json"))
        assert list((root / "history" / "ai-activity").glob("*.md"))
        assert "TASK-001" in (root / "history" / "timeline.md").read_text()

    def test_the_worker_did_not_overstate_the_ai_s_own_result(self, live_run):
        """If the AI qualified its result, the PR must show that."""
        attempt = live_run["summary"].attempts[0]
        pull = live_run["client"].pulls[0]
        if attempt.outcome == Outcome.PARTIAL:
            assert pull["draft"] is True
            assert "[PARTIAL]" in pull["title"]
