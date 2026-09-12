"""End-to-end orchestration (orchestrator/workers/runner.py).

This is TASK-007's required test: "a dry-run mode that exercises claim ->
mock-implement -> handoff without calling a real paid API." It runs the
whole loop against an in-memory GitHub, a real git repository in a temp
directory, and the mock adapter, and asserts what the worker *did* --
which comments it posted, which branch it created, whether a PR was
opened, and what the handoff says.

Every scenario here corresponds to a rule the worker must not break:
losing a claim means writing no code; `execution:human` means writing no
code; an out-of-scope diff means no PR; a failing test suite means no
clean-looking PR.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orchestrator.workers.adapters.base import AIResult, SuiteResult
from orchestrator.workers.adapters.mock import MockAdapter
from orchestrator.workers.claim import format_claim
from orchestrator.workers.config import WorkerConfig
from orchestrator.workers.github import FakeGitHubClient
from orchestrator.workers.gitops import Git
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

**Forbidden paths:**
- `domain/schemas/**`

**Acceptance criteria:**
- [ ] It works
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repository with a real remote.

    The worker really runs git, so the tests do too: a bare repository
    stands in for GitHub, which means `git push` is genuinely exercised
    rather than stubbed into always succeeding.
    """
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


def make_config(repo: Path, **kwargs) -> WorkerConfig:
    defaults = dict(
        worker_id="WORKER-01", repo_root=repo, owner="apache-61", repo="truelock",
        token="fake-token", base_branch="main",
    )
    defaults.update(kwargs)
    return WorkerConfig(**defaults)


class StubValidator(Validator):
    """A validator with a predetermined verdict, so loop tests stay fast."""

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


def build_runner(repo, client, *, adapter=None, ok=True, dry_run=False, limits=None, **config_kwargs):
    config = make_config(repo, dry_run=dry_run, **config_kwargs)
    return WorkerRunner(
        config,
        client,
        adapter or MockAdapter(write_files=True),
        limits=limits or RunLimits(once=True),
        git=Git(repo, dry_run=dry_run),
        validator=StubValidator(repo, ok=ok),
        log=lambda *_: None,
    )


class WritingAdapter(MockAdapter):
    """A mock that writes specific files, to drive scope scenarios."""

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
            task_id=task_id,
            status=self.status,
            summary="Wrote the requested files.",
            changed_files=list(self.files),
            tests=SuiteResult(passed=3),
            next_recommended_tasks=["TASK-002"],
        )


class TestHappyPath:
    def setup_method(self):
        self.adapter = WritingAdapter({"domain/entities/invoice.py": "class Invoice:\n    pass\n"})

    def test_full_loop_reaches_a_pull_request(self, repo, client):
        runner = build_runner(repo, client, adapter=self.adapter)
        summary = runner.run()

        assert len(summary.attempts) == 1
        attempt = summary.attempts[0]
        assert attempt.outcome == Outcome.DONE
        assert attempt.pr_url
        assert summary.exit_code == 0

    def test_it_claims_before_it_works(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        bodies = [comment["body"] for comment in client.list_comments(1)]
        assert bodies[0].startswith("CLAIM\n")
        assert "worker_id: WORKER-01" in bodies[0]

    def test_it_creates_an_isolated_branch_and_never_touches_main(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        git = Git(repo)
        assert git.current_branch() == "feature/TASK-001-canonical-ingestion"
        main_files = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.split()
        assert "domain/entities/invoice.py" not in main_files

    def test_it_commits_the_work(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=repo,
                             capture_output=True, text=True, check=True).stdout
        assert "TASK-001" in log

    def test_it_writes_the_history_entry(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        entries = list((repo / "history" / "ai-activity").glob("*.md"))
        assert len(entries) == 1
        text = entries[0].read_text()
        for heading in ("## Goal", "## Changes", "## Tests", "## Known issues"):
            assert heading in text
        assert "WORKER-01" in text
        assert "feature/TASK-001-canonical-ingestion" in text

    def test_it_appends_one_timeline_line(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        timeline = (repo / "history" / "timeline.md").read_text()
        assert "TASK-001" in timeline
        assert "WORKER-01" in timeline

    def test_it_writes_the_machine_readable_handoff(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        results = list((repo / ".state").glob("task-result-*.json"))
        assert len(results) == 1
        payload = json.loads(results[0].read_text())
        assert payload["task_id"] == "TASK-001"
        assert payload["status"] == "DONE"
        assert payload["next_recommended_tasks"] == ["TASK-002"]

    def test_the_pr_body_carries_everything_a_reviewer_needs(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        body = client.pulls[0]["body"]
        for section in ("## Task", "## Objective", "## Summary", "## Changed files",
                        "## Tests", "## Risks", "## Contract impact",
                        "## Documentation updated", "## Related decisions",
                        "## AI worker", "## Handoff"):
            assert section in body, section
        assert "TASK-001" in body
        assert "WORKER-01" in body

    def test_a_passing_run_opens_a_normal_pr_not_a_draft(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        assert client.pulls[0]["draft"] is False

    def test_it_updates_the_issue_state(self, repo, client):
        build_runner(repo, client, adapter=self.adapter).run()
        labels = {label["name"] for label in client.get_issue(1)["labels"]}
        assert "status:review" in labels
        assert "status:ready" not in labels

    def test_it_never_merges(self, repo, client):
        """TASK-007 acceptance criterion, asserted at the loop level."""
        build_runner(repo, client, adapter=self.adapter).run()
        assert not any("merge" in call.path.lower() for call in client.recorded)

    def test_it_records_the_routing_decision(self, repo, client):
        runner = build_runner(repo, client, adapter=self.adapter)
        runner.run()
        assert runner.router.events
        assert runner.router.events[0].render().startswith("ROUTING_EVENT ")
        assert client.pulls[0]["body"].count("ROUTING_EVENT") >= 1

    def test_it_records_usage_against_the_ledger(self, repo, client):
        runner = build_runner(repo, client, adapter=self.adapter)
        runner.run()
        assert len(runner.ledger.entries) == 1
        assert runner.ledger.entries[0].project == "claude-code-cli"


class RacingClient(FakeGitHubClient):
    """A GitHub double where another worker wins the race.

    The competing claim is injected with a *lower* comment id at the
    moment our worker posts its own, which is exactly the situation the
    protocol exists for: both workers read READY, both post, and only the
    server's ordering decides. It is invisible until the worker re-reads.
    """

    def __init__(self, rival: str = "WORKER-09") -> None:
        super().__init__()
        self.rival = rival
        self._raced = False

    def add_comment(self, number: int, body: str) -> dict:
        if body.startswith("CLAIM\n") and not self._raced:
            self._raced = True
            self.comments.setdefault(number, []).append(
                {"id": 1, "body": format_claim("TASK-001", self.rival, "rival-claim", "t")}
            )
        return super().add_comment(number, body)


class TestLostClaim:
    """The single most important rule: two workers never both execute one task."""

    @pytest.fixture
    def racing(self) -> RacingClient:
        client = RacingClient()
        client.add_issue(1, "TASK-001: Canonical ingestion", TASK_BODY, ["status:ready"])
        return client

    def test_a_worker_that_loses_writes_no_code(self, repo, racing):
        adapter = WritingAdapter({"domain/entities/invoice.py": "nope"})
        summary = build_runner(repo, racing, adapter=adapter).run()

        assert summary.attempts[0].outcome == Outcome.LOST_CLAIM
        assert adapter.calls == []                       # the AI was never invoked
        assert not (repo / "domain" / "entities" / "invoice.py").exists()
        assert Git(repo).current_branch() == "main"      # no branch was created
        assert racing.pulls == []                        # no PR

    def test_the_loser_withdraws_its_claim(self, repo, racing):
        build_runner(repo, racing).run()
        bodies = [comment["body"] for comment in racing.list_comments(1)]
        assert any(body.startswith("CLAIM-WITHDRAWN") for body in bodies)

    def test_the_loser_names_the_winner(self, repo, racing):
        summary = build_runner(repo, racing).run()
        assert "WORKER-09" in summary.attempts[0].reason

    def test_a_task_already_claimed_by_another_worker_is_never_attempted(self, repo, client):
        """Cheaper than losing a race: the eligibility gate skips a task
        someone already holds, so no second claim comment is even posted."""
        client.comments[1].append(
            {"id": 1, "body": format_claim("TASK-001", "WORKER-09", "x", "t")}
        )
        adapter = WritingAdapter({"domain/entities/invoice.py": "nope"})
        summary = build_runner(repo, client, adapter=adapter).run()

        assert summary.attempts == []
        assert "already claimed by WORKER-09" in summary.stop_reason
        assert adapter.calls == []
        assert client.pulls == []


class TestHumanAuthorization:
    BODY = TASK_BODY.replace("**Human authorization required:** No",
                             "**Human authorization required:** Yes")

    def test_it_proposes_and_writes_no_code(self, repo, client):
        client.issues[1]["body"] = self.BODY
        adapter = WritingAdapter({"domain/entities/invoice.py": "nope"})
        summary = build_runner(repo, client, adapter=adapter).run()

        assert summary.attempts[0].outcome == Outcome.PROPOSAL
        assert adapter.calls == []
        assert not (repo / "domain" / "entities" / "invoice.py").exists()
        assert Git(repo).current_branch() == "main"
        assert client.pulls == []

    def test_the_proposal_is_posted_on_the_issue(self, repo, client):
        client.issues[1]["body"] = self.BODY
        build_runner(repo, client).run()
        bodies = [comment["body"] for comment in client.list_comments(1)]
        proposal = next(body for body in bodies if body.startswith("PROPOSAL"))
        assert "no code was written" in proposal
        assert "CONTRIBUTING.md" in proposal

    def test_the_task_is_released_for_a_human(self, repo, client):
        client.issues[1]["body"] = self.BODY
        build_runner(repo, client).run()
        bodies = [comment["body"] for comment in client.list_comments(1)]
        assert any(body.startswith("RELEASE") for body in bodies)


class TestScopeViolation:
    def test_an_out_of_scope_change_blocks_instead_of_opening_a_pr(self, repo, client):
        adapter = WritingAdapter({
            "domain/entities/invoice.py": "ok\n",
            "domain/schemas/invoice.schema.json": "{}\n",   # forbidden
        })
        summary = build_runner(repo, client, adapter=adapter).run()

        assert summary.attempts[0].outcome == Outcome.BLOCKED
        assert client.pulls == []

    def test_it_explains_what_was_out_of_scope(self, repo, client):
        adapter = WritingAdapter({
            "domain/entities/invoice.py": "ok\n",
            "frontend/app.tsx": "nope\n",
        })
        build_runner(repo, client, adapter=adapter).run()
        blocked = next(comment["body"] for comment in client.list_comments(1)
                       if comment["body"].startswith("BLOCKED"))
        assert "frontend/app.tsx" in blocked
        assert "allowed_paths" in blocked
        assert "widening its own scope" in blocked

    def test_the_issue_is_labelled_blocked(self, repo, client):
        adapter = WritingAdapter({"frontend/app.tsx": "nope\n"})
        build_runner(repo, client, adapter=adapter).run()
        labels = {label["name"] for label in client.get_issue(1)["labels"]}
        assert "status:blocked" in labels


class TestValidationFailure:
    def test_a_failing_suite_never_produces_a_clean_looking_pr(self, repo, client):
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        summary = build_runner(repo, client, adapter=adapter, ok=False).run()

        attempt = summary.attempts[0]
        assert attempt.outcome == Outcome.FAILED
        assert summary.exit_code == 1
        pull = client.pulls[0]
        assert pull["draft"] is True
        assert "VALIDATION FAILED" in pull["title"]

    def test_the_failure_is_recorded_in_the_handoff_and_history(self, repo, client):
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        build_runner(repo, client, adapter=adapter, ok=False).run()
        payload = json.loads(next((repo / ".state").glob("task-result-*.json")).read_text())
        assert payload["status"] == "FAILED"
        history = next((repo / "history" / "ai-activity").glob("*.md")).read_text()
        assert "FAILED" in history

    def test_the_issue_is_marked_blocked_not_in_review(self, repo, client):
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        build_runner(repo, client, adapter=adapter, ok=False).run()
        labels = {label["name"] for label in client.get_issue(1)["labels"]}
        assert "status:blocked" in labels
        assert "status:review" not in labels


class TestAdapterFailure:
    class BrokenAdapter(MockAdapter):
        def execute(self, prompt, *, task_id, workdir, timeout=0):
            from orchestrator.workers.adapters.base import AdapterError

            raise AdapterError("the CLI exited 1")

    def test_an_adapter_error_fails_the_task_without_a_pr(self, repo, client):
        summary = build_runner(repo, client, adapter=self.BrokenAdapter()).run()
        assert summary.attempts[0].outcome == Outcome.FAILED
        assert client.pulls == []

    def test_the_error_is_recorded_on_the_issue(self, repo, client):
        build_runner(repo, client, adapter=self.BrokenAdapter()).run()
        bodies = [comment["body"] for comment in client.list_comments(1)]
        assert any("WORKER FAILED" in body and "the CLI exited 1" in body for body in bodies)

    def test_the_failed_call_is_recorded_in_the_ledger(self, repo, client):
        runner = build_runner(repo, client, adapter=self.BrokenAdapter())
        runner.run()
        assert runner.ledger.entries[0].status == "error"


class TestDryRun:
    """TASK-007's required test: claim -> mock-implement -> handoff, with
    no paid API call and no side effects."""

    def test_it_leaves_the_repository_untouched(self, repo, client):
        before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                capture_output=True, text=True, check=True).stdout
        adapter = MockAdapter(write_files=False)
        summary = build_runner(repo, client, adapter=adapter, dry_run=True).run()

        after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                               capture_output=True, text=True, check=True).stdout
        assert before == after                                   # no commit
        assert Git(repo).is_clean()                              # no stray files
        assert not list((repo / "history" / "ai-activity").glob("*.md"))
        assert not (repo / ".state").exists()
        assert summary.attempts                                  # but it did run

    def test_a_dry_run_client_records_writes_instead_of_sending_them(self):
        """Dry-run safety is a property of the client, not a promise the
        runner keeps: `DryRunGitHubClient` cannot write, by construction."""
        from orchestrator.workers.github import DryRunGitHubClient

        client = DryRunGitHubClient("apache-61", "truelock", "token")
        client.add_labels(1, ["status:claimed"])
        assert client.recorded[0].method == "POST"
        assert "labels" in client.recorded[0].path

    def test_a_simulated_claim_is_visible_to_the_verify_that_follows(self):
        """Without the local overlay, a rehearsed CLAIM would be invisible
        to VERIFY and every dry run would stop at 'lost the claim'."""
        from orchestrator.workers.claim import find_winning_claim, format_claim
        from orchestrator.workers.github import DryRunGitHubClient

        client = DryRunGitHubClient("apache-61", "truelock", "token")
        client.list_comments = lambda number, per_page=100: list(  # type: ignore[assignment]
            client._simulated_comments.get(number, [])
        )
        body = format_claim("TASK-001", "WORKER-01", "mine", "t")
        client._write("POST", "/repos/apache-61/truelock/issues/1/comments", {"body": body})
        winner = find_winning_claim(client.list_comments(1))
        assert winner is not None and winner.claim_id == "mine"

    def test_a_real_competing_claim_still_beats_a_simulated_one(self):
        """Simulated comments sort last, so a rehearsal against a task
        someone else holds correctly reports LOST rather than a false win."""
        from orchestrator.workers.claim import find_winning_claim, format_claim
        from orchestrator.workers.github import DryRunGitHubClient

        client = DryRunGitHubClient("apache-61", "truelock", "token")
        real = {"id": 42, "body": format_claim("TASK-001", "WORKER-09", "theirs", "t")}
        client._write(
            "POST",
            "/repos/apache-61/truelock/issues/1/comments",
            {"body": format_claim("TASK-001", "WORKER-01", "mine", "t")},
        )
        simulated = client._simulated_comments[1]
        assert find_winning_claim([real, *simulated]).claim_id == "theirs"

    def test_the_adapter_still_runs_so_the_loop_is_really_exercised(self, repo, client):
        adapter = MockAdapter(write_files=False)
        build_runner(repo, client, adapter=adapter, dry_run=True).run()
        assert adapter.calls == ["TASK-001"]
        assert "Path budget" in adapter.last_prompt

    def test_no_paid_api_is_involved(self, repo, client):
        adapter = MockAdapter(write_files=False)
        build_runner(repo, client, adapter=adapter, dry_run=True).run()
        assert adapter.name == "mock"


class TestLimits:
    def _two_ready_tasks(self, client):
        client.add_issue(2, "TASK-002: Second", TASK_BODY, ["status:ready"])

    def test_once_attempts_exactly_one_task(self, repo, client):
        self._two_ready_tasks(client)
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        summary = build_runner(repo, client, adapter=adapter,
                               limits=RunLimits(once=True)).run()
        assert len(summary.attempts) == 1
        assert "--once" in summary.stop_reason

    def test_max_tasks_bounds_a_continuous_run(self, repo, client):
        self._two_ready_tasks(client)
        client.add_issue(3, "TASK-003: Third", TASK_BODY, ["status:ready"])
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        summary = build_runner(repo, client, adapter=adapter,
                               limits=RunLimits(max_tasks=2)).run()
        assert len(summary.attempts) == 2
        assert "--max-tasks 2" in summary.stop_reason

    def test_an_empty_queue_stops_the_loop(self, repo, client):
        client.issues[1]["state"] = "closed"
        summary = build_runner(repo, client, limits=RunLimits(max_tasks=5)).run()
        assert summary.attempts == []
        assert "No eligible READY task" in summary.stop_reason

    def test_a_blocker_stops_a_continuous_run(self, repo, client):
        """A human should look before more work piles up behind a blocker."""
        self._two_ready_tasks(client)
        adapter = WritingAdapter({"frontend/app.tsx": "out of scope\n"})
        summary = build_runner(repo, client, adapter=adapter,
                               limits=RunLimits(max_tasks=5)).run()
        assert len(summary.attempts) == 1
        assert summary.attempts[0].outcome == Outcome.BLOCKED
        assert "BLOCKED" in summary.stop_reason


class TestContextIsBounded:
    def test_the_prompt_carries_the_task_not_the_project_history(self, repo, client):
        adapter = MockAdapter(write_files=False)
        build_runner(repo, client, adapter=adapter, dry_run=True).run()
        prompt = adapter.last_prompt

        assert "TASK-001" in prompt
        assert "Path budget" in prompt
        assert "domain/entities/**" in prompt
        assert "Required output" in prompt
        # The bounded-context rule: the pack is a task brief, not a dump.
        assert len(prompt) < 80_000


class TestUnverifiedRun:
    """A change nothing ran against is a draft, not a review-ready PR."""

    class SkippingValidator(Validator):
        def run(self, *, changed_paths=None) -> ValidationReport:
            report = ValidationReport()
            report.add(GateResult("unit tests", "skipped", "pytest -q tests/unit",
                                  "pytest is not installed on this worker"))
            return report

    def runner(self, repo, client):
        config = make_config(repo)
        return WorkerRunner(
            config,
            client,
            WritingAdapter({"domain/entities/invoice.py": "ok\n"}),
            limits=RunLimits(once=True),
            git=Git(repo),
            validator=self.SkippingValidator(repo),
            log=lambda *_: None,
        )

    def test_the_pr_is_a_draft_marked_unverified(self, repo, client):
        self.runner(repo, client).run()
        pull = client.pulls[0]
        assert pull["draft"] is True
        assert "UNVERIFIED" in pull["title"]

    def test_the_body_says_nothing_was_verified(self, repo, client):
        self.runner(repo, client).run()
        assert "Nothing was verified" in client.pulls[0]["body"]

    def test_the_handoff_does_not_claim_a_pass(self, repo, client):
        self.runner(repo, client).run()
        payload = json.loads(next((repo / ".state").glob("task-result-*.json")).read_text())
        assert "NOT VERIFIED" in payload["run"]["validation"]


class TestAiQualifiedResults:
    """The worker never upgrades the AI's own assessment.

    Both cases here were found by running the loop against the real
    Claude Code CLI: passing tests were silently promoting a
    self-declared PARTIAL to DONE, and a run the AI explicitly flagged
    for human review was opening as a normal, merge-ready PR.
    """

    def build(self, repo, client, *, status="PARTIAL", human_review=False):
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"}, status=status)
        original = adapter.execute

        def execute(prompt, *, task_id, workdir, timeout=0):
            result = original(prompt, task_id=task_id, workdir=workdir, timeout=timeout)
            result.requires_human_review = human_review
            result.known_issues = ["the tests were reasoned through, not run"]
            return result

        adapter.execute = execute
        return build_runner(repo, client, adapter=adapter, ok=True)

    def test_partial_is_not_promoted_to_done_by_passing_tests(self, repo, client):
        """Passing tests prove what was written works, not that what was
        asked for got written."""
        summary = self.build(repo, client).run()
        assert summary.attempts[0].outcome == Outcome.PARTIAL

    def test_a_partial_pr_is_a_draft_and_says_so(self, repo, client):
        self.build(repo, client).run()
        pull = client.pulls[0]
        assert pull["draft"] is True
        assert "[PARTIAL]" in pull["title"]

    def test_the_handoff_records_partial(self, repo, client):
        self.build(repo, client).run()
        payload = json.loads(next((repo / ".state").glob("task-result-*.json")).read_text())
        assert payload["status"] == "PARTIAL"

    def test_a_run_flagged_for_human_review_is_not_merge_ready(self, repo, client):
        self.build(repo, client, status="DONE", human_review=True).run()
        pull = client.pulls[0]
        assert pull["draft"] is True
        assert "NEEDS HUMAN REVIEW" in pull["title"]
        assert "asked for human review" in pull["body"]

    def test_an_unqualified_done_still_opens_a_normal_pr(self, repo, client):
        """The guard must not make every PR a draft."""
        summary = self.build(repo, client, status="DONE", human_review=False).run()
        assert summary.attempts[0].outcome == Outcome.DONE
        assert client.pulls[0]["draft"] is False


class TestWorkerScratchStaysOutOfThePr:
    """`.state/` is runtime scratch, never a source of truth.

    `.gitignore` covers it in this repository, but a commit that relies on
    the host repo's ignore rules leaks the worker's own bookkeeping into
    someone's review wherever those rules differ — which is exactly what
    the first live integration run did.
    """

    def test_state_files_are_never_committed(self, repo, client):
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        build_runner(repo, client, adapter=adapter).run()

        assert list((repo / ".state").glob("task-result-*.json")), "scratch should exist on disk"
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.split()
        assert not [path for path in tracked if path.startswith(".state/")]

    def test_the_durable_history_entry_is_still_committed(self, repo, client):
        """Excluding scratch must not exclude the record CONTRIBUTING §6 requires."""
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        build_runner(repo, client, adapter=adapter).run()
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.split()
        assert any(path.startswith("history/ai-activity/") for path in tracked)

    def test_scratch_does_not_block_the_next_task(self, repo, client):
        """Leaving `.state/` on disk must not make the tree look dirty to
        the following task — the worker would refuse to start and strand
        a continuous run after exactly one task."""
        client.add_issue(2, "TASK-002: Second", TASK_BODY, ["status:ready"])
        adapter = WritingAdapter({"domain/entities/invoice.py": "ok\n"})
        summary = build_runner(repo, client, adapter=adapter,
                               limits=RunLimits(max_tasks=2)).run()

        assert len(summary.attempts) == 2
        assert all(attempt.outcome == Outcome.DONE for attempt in summary.attempts)
        assert Git(repo).is_clean()

    def test_real_uncommitted_work_still_counts_as_dirty(self, repo, client):
        """The exemption is for worker scratch only; a stray edit must
        still stop a task from starting on top of it."""
        (repo / "stray.py").write_text("x = 1\n")
        assert not Git(repo).is_clean()

    def test_nested_build_artifacts_are_not_committed(self, repo, client):
        """`__pycache__` appears at every level of a tree, and the worker
        creates it itself by running the validation gates."""
        class ArtifactAdapter(WritingAdapter):
            def execute(self, prompt, *, task_id, workdir, timeout=0):
                result = super().execute(prompt, task_id=task_id, workdir=workdir,
                                         timeout=timeout)
                for relative in ("__pycache__/root.pyc",
                                 "domain/entities/__pycache__/nested.pyc",
                                 ".pytest_cache/v/cache/lastfailed"):
                    path = Path(workdir) / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("artifact\n")
                return result

        adapter = ArtifactAdapter({"domain/entities/invoice.py": "ok\n"})
        build_runner(repo, client, adapter=adapter).run()

        tracked = subprocess.run(
            ["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.split()
        assert not [path for path in tracked if Git.is_scratch(path)], tracked
        assert "domain/entities/invoice.py" in tracked

    def test_is_scratch_matches_at_any_depth_but_not_lookalikes(self):
        assert Git.is_scratch(".state/usage.jsonl")
        assert Git.is_scratch("__pycache__/x.pyc")
        assert Git.is_scratch("a/b/__pycache__/x.pyc")
        assert Git.is_scratch(".pytest_cache/v/cache/lastfailed")
        assert not Git.is_scratch("domain/entities/invoice.py")
        assert not Git.is_scratch("mystate/file.py")
        assert not Git.is_scratch("docs/__pycache__notes.md")
