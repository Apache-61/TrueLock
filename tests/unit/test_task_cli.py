"""Unit tests for the claim/verify race-detection logic in
scripts/orchestration/task_cli.py (tasks/README.md -> Claim protocol,
history/decisions/ADR-0003-task-coordination.md).

Loaded via importlib rather than a package import, since scripts/ is a
collection of standalone tools, not an installable package.
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "orchestration" / "task_cli.py"

spec = importlib.util.spec_from_file_location("task_cli", MODULE_PATH)
task_cli = importlib.util.module_from_spec(spec)
sys.modules["task_cli"] = task_cli
spec.loader.exec_module(task_cli)


def _claim_comment(comment_id, worker_id, claim_id, task_id="TASK-004"):
    return {
        "id": comment_id,
        "body": (
            f"CLAIM\n"
            f"task_id: {task_id}\n"
            f"worker_id: {worker_id}\n"
            f"claim_id: {claim_id}\n"
            f"timestamp: 2026-09-12T14:00:00+00:00\n"
        ),
    }


def test_no_claims_returns_none():
    assert task_cli.find_earliest_claim([]) is None
    assert task_cli.find_earliest_claim([{"id": 1, "body": "just a regular comment"}]) is None


def test_single_claim_wins():
    comments = [_claim_comment(100, "WORKER-01", "claim-a")]
    result = task_cli.find_earliest_claim(comments)
    assert result["claim_id"] == "claim-a"
    assert result["worker_id"] == "WORKER-01"


def test_earliest_comment_id_wins_regardless_of_list_order():
    """Two workers claim near-simultaneously; the earlier GitHub comment
    id (server-assigned) must win even if it's not first in the list."""
    comments = [
        _claim_comment(205, "WORKER-02", "claim-b"),  # posted second
        _claim_comment(204, "WORKER-01", "claim-a"),  # posted first
    ]
    result = task_cli.find_earliest_claim(comments)
    assert result["claim_id"] == "claim-a"
    assert result["worker_id"] == "WORKER-01"


def test_non_claim_comments_are_ignored():
    comments = [
        {"id": 1, "body": "looks good to me"},
        _claim_comment(2, "WORKER-03", "claim-c"),
        {"id": 3, "body": "RELEASE\nworker_id: WORKER-01\n"},
    ]
    result = task_cli.find_earliest_claim(comments)
    assert result["claim_id"] == "claim-c"
