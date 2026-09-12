"""The CLAIM -> VERIFY protocol (orchestrator/workers/claim.py).

This is the property the whole multi-worker setup depends on: **two
workers must never both execute one task** (`tasks/README.md`,
ADR-0003). These tests cover the race directly, including the cases
where the losing worker's claim arrives first in the returned list, and
the compatibility requirement that a human running
`scripts/orchestration/task_cli.py` competes correctly against a worker
running `worker start`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


from orchestrator.workers.claim import (
    CLAIM_PATTERN,
    claim_task,
    find_winning_claim,
    format_claim,
    parse_claims,
    release_task,
    withdraw_claim,
)
from orchestrator.workers.github import FakeGitHubClient
from orchestrator.workers.tasks import parse_issue

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_task_cli():
    """Load the standalone manual tool the way its own test does."""
    path = REPO_ROOT / "scripts" / "orchestration" / "task_cli.py"
    spec = importlib.util.spec_from_file_location("task_cli_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["task_cli_compat"] = module
    spec.loader.exec_module(module)
    return module


def claim_comment(comment_id, worker_id, claim_id, task_id="TASK-004"):
    return {
        "id": comment_id,
        "body": format_claim(task_id, worker_id, claim_id, "2026-09-12T14:00:00+00:00"),
    }


class TestFindWinningClaim:
    def test_no_comments_means_unclaimed(self):
        assert find_winning_claim([]) is None

    def test_chatter_is_not_a_claim(self):
        assert find_winning_claim([{"id": 1, "body": "looks good to me"}]) is None

    def test_lowest_comment_id_wins_regardless_of_list_order(self):
        """GitHub assigns comment IDs monotonically server-side; that
        ordering, not the worker's clock and not list order, decides."""
        comments = [
            claim_comment(205, "WORKER-02", "claim-b"),
            claim_comment(204, "WORKER-01", "claim-a"),
        ]
        winner = find_winning_claim(comments)
        assert winner.worker_id == "WORKER-01"
        assert winner.claim_id == "claim-a"

    def test_four_way_race_has_exactly_one_winner(self):
        comments = [claim_comment(300 + i, f"WORKER-0{i}", f"claim-{i}") for i in range(1, 5)]
        winners = {find_winning_claim(comments).claim_id for _ in range(5)}
        assert winners == {"claim-1"}

    def test_release_frees_the_task_for_a_later_claim(self):
        """Without honouring RELEASE, a released task stays owned forever
        by its stale first claim and no worker can ever pick it up."""
        comments = [
            claim_comment(100, "WORKER-01", "claim-a"),
            {"id": 101, "body": "RELEASE\nworker_id: WORKER-01\ntimestamp: t\n"},
            claim_comment(102, "WORKER-02", "claim-b"),
        ]
        winner = find_winning_claim(comments)
        assert winner.worker_id == "WORKER-02"

    def test_release_with_no_later_claim_leaves_the_task_free(self):
        comments = [
            claim_comment(100, "WORKER-01", "claim-a"),
            {"id": 101, "body": "RELEASE\nworker_id: WORKER-01\n"},
        ]
        assert find_winning_claim(comments) is None

    def test_withdrawn_claim_is_skipped(self):
        comments = [
            claim_comment(100, "WORKER-01", "claim-a"),
            {"id": 101, "body": "CLAIM-WITHDRAWN\nclaim_id: claim-a\nworker_id: WORKER-01\n"},
            claim_comment(102, "WORKER-02", "claim-b"),
        ]
        assert find_winning_claim(comments).claim_id == "claim-b"

    def test_parse_claims_is_ordered_by_comment_id(self):
        claims = parse_claims([
            claim_comment(9, "WORKER-03", "c"),
            claim_comment(2, "WORKER-01", "a"),
            claim_comment(5, "WORKER-02", "b"),
        ])
        assert [claim.claim_id for claim in claims] == ["a", "b", "c"]


class TestProtocolCompatibilityWithTaskCli:
    """A human using the manual script and a worker must contend correctly.

    They are separate implementations by design (the script is
    stdlib-only and standalone), so the shared wire format is asserted
    here rather than assumed.
    """

    def test_worker_claim_is_readable_by_task_cli(self):
        task_cli = load_task_cli()
        body = format_claim("TASK-004", "WORKER-01", "claim-a", "2026-09-12T14:00:00+00:00")
        match = task_cli.CLAIM_PATTERN.search(body)
        assert match is not None
        assert match.group("worker_id") == "WORKER-01"
        assert match.group("claim_id") == "claim-a"

    def test_task_cli_claim_is_readable_by_the_worker(self):
        task_cli = load_task_cli()
        body = (
            "CLAIM\ntask_id: TASK-004\nworker_id: WORKER-02\n"
            "claim_id: claim-b\ntimestamp: 2026-09-12T14:00:01+00:00\n"
        )
        assert task_cli.CLAIM_PATTERN.search(body) is not None
        assert CLAIM_PATTERN.search(body) is not None
        winner = find_winning_claim([{"id": 1, "body": body}])
        assert winner.worker_id == "WORKER-02"

    def test_both_implementations_pick_the_same_winner(self):
        task_cli = load_task_cli()
        comments = [
            claim_comment(205, "WORKER-02", "claim-b"),
            claim_comment(204, "WORKER-01", "claim-a"),
        ]
        assert task_cli.find_earliest_claim(comments)["claim_id"] == "claim-a"
        assert find_winning_claim(comments).claim_id == "claim-a"


class TestClaimTaskRoundTrip:
    def setup_method(self):
        self.client = FakeGitHubClient()
        self.client.add_issue(4, "TASK-004: Detectors", "**Priority:** P0\n", ["status:ready"])
        self.task = parse_issue(self.client.get_issue(4))

    def test_uncontested_claim_wins(self):
        outcome = claim_task(self.client, self.task, "WORKER-01")
        assert outcome.won is True
        assert outcome.winner.worker_id == "WORKER-01"
        assert "earliest live CLAIM" in outcome.reason

    def test_second_worker_loses_and_says_who_won(self):
        first = claim_task(self.client, self.task, "WORKER-01")
        second = claim_task(self.client, self.task, "WORKER-02")
        assert first.won is True
        assert second.won is False
        assert "WORKER-01" in second.reason
        assert first.claim_id != second.claim_id

    def test_verify_re_reads_rather_than_trusting_the_post(self):
        """A claim that lands after ours must still be able to beat us if
        GitHub ordered it first -- which is only observable by re-reading."""
        interloper = claim_comment(1, "WORKER-09", "earlier-claim")
        self.client.comments[4].append(interloper)
        outcome = claim_task(self.client, self.task, "WORKER-01")
        assert outcome.won is False
        assert outcome.winner.worker_id == "WORKER-09"

    def test_losing_worker_withdraws_so_the_thread_stays_honest(self):
        outcome = claim_task(self.client, self.task, "WORKER-02")
        withdraw_claim(self.client, 4, outcome.claim_id, "WORKER-02", "lost the race")
        bodies = [comment["body"] for comment in self.client.list_comments(4)]
        assert any(body.startswith("CLAIM-WITHDRAWN") for body in bodies)

    def test_release_returns_the_task_to_the_queue(self):
        claim_task(self.client, self.task, "WORKER-01")
        release_task(self.client, 4, "WORKER-01", "execution:human")
        assert find_winning_claim(self.client.list_comments(4)) is None


class TestClaimFormat:
    def test_every_required_field_is_present(self):
        """tasks/README.md fixes these four fields; a missing one makes
        the claim unattributable after the fact."""
        body = format_claim("TASK-004", "WORKER-01", "abc-123", "2026-09-12T14:03:00Z")
        assert body.startswith("CLAIM\n")
        for line in ("task_id: TASK-004", "worker_id: WORKER-01",
                     "claim_id: abc-123", "timestamp: 2026-09-12T14:03:00Z"):
            assert line in body

    def test_claim_ids_are_unique_per_call(self):
        from orchestrator.workers.claim import new_claim_id

        assert len({new_claim_id() for _ in range(100)}) == 100
